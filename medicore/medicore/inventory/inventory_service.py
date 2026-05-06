from __future__ import annotations
from decimal import Decimal
from datetime import datetime
from medicore.db.connection import get_db_cursor

def log_inventory_transaction(cursor, item_id: int, trans_type: str, qty: float, ref_type: str, ref_id: str | None = None, note: str | None = None, user_id: int | None = None, batch_number: str | None = None):
    """
    Logs a stock transaction into the inventory_transactions table.
    Captures before and after snapshots for audit safety.
    """
    if not user_id:
        user_id = 1 # Fallback to admin if not provided
        
    # Get current stock (before_qty)
    cursor.execute("SELECT quantity_on_hand FROM inventory_items WHERE item_id = %s", (item_id,))
    row = cursor.fetchone()
    before_qty = Decimal(str(row['quantity_on_hand'] if row else 0))
    
    # Calculate after_qty
    # For OUT/USED/SALE/DAMAGE/EXPIRED, qty is subtracted. For IN/RETURN, it's added.
    # Note: adjustment qty passed should already follow sign convention normally, 
    # but here we follow the transaction type.
    
    change = Decimal(str(qty))
    if trans_type in ['OUT', 'USED', 'SALE', 'DAMAGE', 'EXPIRED']:
        after_qty = before_qty - abs(change)
        final_qty_val = -abs(change)
    elif trans_type in ['IN', 'RETURN', 'REVERSAL']:
        after_qty = before_qty + abs(change)
        final_qty_val = abs(change)
    else: # ADJUST (could be positive or negative)
        after_qty = before_qty + change
        final_qty_val = change
        
    query = """
        INSERT INTO inventory_transactions (
            inventory_item_id, transaction_type, quantity, before_qty, after_qty, 
            reference_type, reference_id, batch_number, note, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (
        item_id, trans_type, final_qty_val, before_qty, after_qty, 
        ref_type, ref_id, batch_number, note, user_id
    ))

def decrease_fifo_stock_for_item(cursor, item_id: int, qty_to_reduce: Decimal):
    """
    Deducts stock using FIFO from stock_batches.
    Updates the stock_batches records reducing quantity_remaining.
    It does not log inventory transactions or touch inventory_items.quantity_on_hand.
    """
    cursor.execute("""
        SELECT batch_id, quantity_remaining 
        FROM stock_batches 
        WHERE inventory_item_id = %s AND quantity_remaining > 0
        ORDER BY received_at ASC
    """, (item_id,))
    batches = cursor.fetchall()
    
    remaining_to_deduct = qty_to_reduce
    
    for batch in batches:
        if remaining_to_deduct <= 0:
            break
            
        batch_qty = Decimal(str(batch['quantity_remaining']))
        
        if batch_qty >= remaining_to_deduct:
            cursor.execute("""
                UPDATE stock_batches SET quantity_remaining = quantity_remaining - %s WHERE batch_id = %s
            """, (remaining_to_deduct, batch['batch_id']))
            remaining_to_deduct = Decimal('0')
            break
        else:
            cursor.execute("""
                UPDATE stock_batches SET quantity_remaining = 0 WHERE batch_id = %s
            """, (batch['batch_id'],))
            remaining_to_deduct -= batch_qty

def get_fifo_selling_price(item_id: int, fallback_price: float = 0.0) -> float:
    """Returns the selling price from the oldest available stock batch."""
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("""
            SELECT selling_price
            FROM stock_batches
            WHERE inventory_item_id = %s AND quantity_remaining > 0
            ORDER BY received_at ASC LIMIT 1
        """, (item_id,))
        batch = cursor.fetchone()
        if batch:
            return float(batch['selling_price'])
        
        # Fallback to master item
        cursor.execute("SELECT selling_price FROM inventory_items WHERE item_id = %s", (item_id,))
        master = cursor.fetchone()
        if master and master['selling_price'] is not None:
            return float(master['selling_price'])
            
        return fallback_price

def reduce_stock_for_service(service_item_id: int, service_qty: int, ref_type: str, ref_id: str, stage: str = 'on_completion', user_id: int | None = None):
    """
    Reduces stock for all inventory items mapped to a given service at a specific stage.
    usage_stage: 'on_bill', 'on_sample_collection', 'on_completion', 'on_dispense'
    """
    mapping_query = """
        SELECT inventory_item_id, quantity_required
        FROM service_inventory_mapping
        WHERE service_item_id = %s AND usage_stage = %s
    """
    
    update_stock_query = """
        UPDATE inventory_items
        SET quantity_on_hand = quantity_on_hand - %s
        WHERE item_id = %s
    """
    
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        # 1. Get all mapped inventory items for this service at this stage
        cursor.execute(mapping_query, (service_item_id, stage))
        mappings = cursor.fetchall() or []
        
        if not mappings:
            return True # No mapping for this stage, no reduction needed
            
        for mapping in mappings:
            item_id = mapping['inventory_item_id']
            qty_to_reduce = Decimal(str(mapping['quantity_required'])) * Decimal(str(service_qty))
            
            # 2. Update stock level
            cursor.execute(update_stock_query, (qty_to_reduce, item_id))
            
            # 3. Reduce FIFO batches
            decrease_fifo_stock_for_item(cursor, item_id, qty_to_reduce)
            
            # 4. Log transaction
            log_inventory_transaction(
                cursor, 
                item_id, 
                'USED', 
                float(qty_to_reduce), 
                ref_type, 
                ref_id, 
                f"Automated usage for service {service_item_id} at stage {stage}",
                user_id
            )
            
    return True

def reduce_stock_for_sale(inventory_item_id: int, qty: float, ref_id: str, user_id: int | None = None, cursor: any = None):
    """
    Directly reduces stock for saleable items (e.g. pharmacy dispensing or billing shop items).
    """
    update_query = """
        UPDATE inventory_items 
        SET quantity_on_hand = quantity_on_hand - %s
        WHERE item_id = %s AND is_saleable = TRUE
    """
    
    if cursor:
        _do_reduce_stock_for_sale(cursor, inventory_item_id, qty, ref_id, user_id, update_query)
        return True
        
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        _do_reduce_stock_for_sale(cursor, inventory_item_id, qty, ref_id, user_id, update_query)
    return True

def _do_reduce_stock_for_sale(cursor, inventory_item_id, qty, ref_id, user_id, update_query):
    cursor.execute(update_query, (qty, inventory_item_id))
    decrease_fifo_stock_for_item(cursor, inventory_item_id, Decimal(str(qty)))
    log_inventory_transaction(
        cursor,
        inventory_item_id,
        'SALE',
        qty,
        'Bill',
        ref_id,
        "Direct inventory sale",
        user_id
    )

def check_stock_alerts():
    """
    Returns items that are below minimum stock level, out of stock, or expiring soon.
    """
    query = """
        SELECT item_id, item_name, item_code, quantity_on_hand, minimum_stock_level, expiry_date, usage_mode
        FROM inventory_items
        WHERE (quantity_on_hand <= minimum_stock_level AND status = 'Active')
           OR (quantity_on_hand <= 0 AND status = 'Active')
           OR (expiry_date IS NOT NULL AND expiry_date <= DATE_ADD(CURDATE(), INTERVAL 30 DAY))
        ORDER BY quantity_on_hand ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []
