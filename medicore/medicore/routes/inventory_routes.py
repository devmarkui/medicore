from __future__ import annotations
from flask import Blueprint, flash, redirect, render_template, request, session, url_for, jsonify
from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token
from medicore.inventory.inventory_service import log_inventory_transaction, check_stock_alerts

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")
ALLOWED_ROLES = ["Admin", "SuperAdmin", "Pharmacist", "LabTechnician"]


# ══════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════

@inventory_bp.get("/dashboard")
@login_required
@role_required(ALLOWED_ROLES)
def inventory_dashboard():
    """Main inventory dashboard — compact real-time UI."""
    alerts = check_stock_alerts()

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("SELECT COUNT(*) as total FROM inventory_items WHERE status = 'Active'")
        total_items = cursor.fetchone()['total']

        cursor.execute("""SELECT COUNT(*) as cnt FROM inventory_items
                          WHERE quantity_on_hand <= 0 AND status = 'Active'""")
        out_of_stock = cursor.fetchone()['cnt']

        cursor.execute("""SELECT COUNT(*) as cnt FROM inventory_items
                          WHERE quantity_on_hand > 0
                            AND quantity_on_hand <= minimum_stock_level
                            AND status = 'Active'""")
        low_stock = cursor.fetchone()['cnt']

        cursor.execute("""SELECT COUNT(*) as cnt FROM inventory_items
                          WHERE expiry_date IS NOT NULL
                            AND expiry_date > CURDATE()
                            AND expiry_date <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)
                            AND status = 'Active'""")
        expiring_soon = cursor.fetchone()['cnt']

        cursor.execute("""SELECT category, COUNT(*) as count
                          FROM inventory_items WHERE status = 'Active'
                          GROUP BY category ORDER BY count DESC""")
        categories = cursor.fetchall() or []

        cursor.execute("""SELECT item_id, item_name, item_code, category, unit,
                                 quantity_on_hand, minimum_stock_level,
                                 selling_price, expiry_date, status, usage_mode
                          FROM inventory_items
                          ORDER BY quantity_on_hand ASC, item_name ASC""")
        all_items = cursor.fetchall() or []

        cursor.execute("""SELECT t.transaction_id, t.transaction_type, t.quantity,
                                 t.reference_type, t.note, t.created_at,
                                 i.item_name, i.item_code,
                                 u.first_name, u.last_name
                          FROM inventory_transactions t
                          JOIN inventory_items i ON t.inventory_item_id = i.item_id
                          JOIN users u ON t.created_by = u.user_id
                          ORDER BY t.created_at DESC
                          LIMIT 10""")
        transactions = cursor.fetchall() or []

    return render_template(
        "inventory/inventory_dashboard.html",
        title="Inventory Dashboard",
        active_page="inventory",
        current_user={"username": session.get("username", "User"), "role": session.get("role", "")},
        alerts=alerts,
        categories=categories,
        all_items=all_items,
        transactions=transactions,
        stats={
            "total_items": total_items,
            "out_of_stock": out_of_stock,
            "low_stock": low_stock,
            "expiring_soon": expiring_soon,
        },
        csrf_token=generate_csrf_token(),
    )


@inventory_bp.get("/api/dashboard-state")
@login_required
@role_required(ALLOWED_ROLES)
def api_dashboard_state():
    """JSON endpoint for auto-refresh polling."""
    alerts = check_stock_alerts()
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("SELECT COUNT(*) as total FROM inventory_items WHERE status = 'Active'")
        total_items = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as cnt FROM inventory_items WHERE quantity_on_hand <= 0 AND status = 'Active'")
        out_of_stock = cursor.fetchone()['cnt']
        cursor.execute("""SELECT COUNT(*) as cnt FROM inventory_items
                          WHERE quantity_on_hand > 0 AND quantity_on_hand <= minimum_stock_level AND status = 'Active'""")
        low_stock = cursor.fetchone()['cnt']
        cursor.execute("""SELECT COUNT(*) as cnt FROM inventory_items
                          WHERE expiry_date IS NOT NULL AND expiry_date > CURDATE()
                            AND expiry_date <= DATE_ADD(CURDATE(), INTERVAL 30 DAY) AND status = 'Active'""")
        expiring_soon = cursor.fetchone()['cnt']
        cursor.execute("""SELECT t.transaction_id, t.transaction_type, t.quantity,
                                 t.reference_type, t.created_at,
                                 i.item_name, u.first_name, u.last_name
                          FROM inventory_transactions t
                          JOIN inventory_items i ON t.inventory_item_id = i.item_id
                          JOIN users u ON t.created_by = u.user_id
                          ORDER BY t.created_at DESC LIMIT 10""")
        recent = cursor.fetchall() or []
    for r in recent:
        if r.get('created_at'):
            r['created_at'] = r['created_at'].strftime('%H:%M · %d %b')
    return jsonify({
        "kpis": {"total_items": total_items, "out_of_stock": out_of_stock,
                 "low_stock": low_stock, "expiring_soon": expiring_soon},
        "alerts_count": len(alerts),
        "recent_activity": recent,
    })


# ══════════════════════════════════════════════════════════════════════
#  MANAGE ITEMS  /inventory/manage-items
# ══════════════════════════════════════════════════════════════════════

@inventory_bp.get("/manage-items")
@login_required
@role_required(ALLOWED_ROLES)
def manage_items():
    """Full inventory management list — search, filter, add item."""
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("""SELECT item_id, item_name, item_code, category, unit,
                                 quantity_on_hand, minimum_stock_level,
                                 buying_price, selling_price, expiry_date,
                                 status, usage_mode, batch_number, created_at
                          FROM inventory_items
                          ORDER BY category, item_name""")
        items = cursor.fetchall() or []

        cursor.execute("SELECT * FROM inventory_categories WHERE is_active = TRUE ORDER BY category_name")
        categories = cursor.fetchall() or []

        cursor.execute("SELECT supplier_id, supplier_name FROM suppliers WHERE status = 'Active' ORDER BY supplier_name")
        suppliers = cursor.fetchall() or []

    return render_template(
        "inventory/manage_items.html",
        title="Manage Inventory",
        active_page="inventory",
        current_user={"username": session.get("username", "User"), "role": session.get("role", "")},
        items=items,
        categories=categories,
        suppliers=suppliers,
        csrf_token=generate_csrf_token(),
    )


@inventory_bp.post("/manage-items/add")
@login_required
@role_required(ALLOWED_ROLES)
def add_item():
    """Create a new inventory master item."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("inventory.manage_items"))

    data = request.form
    usage_mode = data.get("usage_mode", "Internal")
    is_saleable = 1 if usage_mode in ['Sale', 'Both'] else 0
    is_consumable = 1 if data.get("is_consumable") == "on" else 0
    track_expiry = 1 if data.get("track_expiry") == "on" else 0

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("""
            INSERT INTO inventory_items (
                item_name, item_code, brand_name, generic_name, category,
                unit, quantity_on_hand, minimum_stock_level, max_stock_level,
                buying_price, selling_price, batch_number, expiry_date,
                supplier_id, storage_location, is_saleable, is_consumable,
                usage_mode, track_expiry, status, created_by
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Active',%s)
        """, (
            data.get("item_name"), data.get("item_code"),
            data.get("brand_name"), data.get("generic_name"),
            data.get("category"), data.get("unit"),
            data.get("quantity_on_hand", 0), data.get("minimum_stock_level", 10),
            data.get("max_stock_level") or None,
            data.get("buying_price", 0.00), data.get("selling_price", 0.00),
            data.get("batch_number") or None,
            data.get("expiry_date") or None,
            data.get("supplier_id") or None,
            data.get("storage_location") or None,
            is_saleable, is_consumable, usage_mode, track_expiry,
            session.get("user_id", 1)
        ))

    flash("Item added successfully.", "success")
    return redirect(url_for("inventory.manage_items"))


# ══════════════════════════════════════════════════════════════════════
#  ITEM DETAIL  /inventory/item/<id>
# ══════════════════════════════════════════════════════════════════════

@inventory_bp.get("/item/<int:item_id>")
@login_required
@role_required(ALLOWED_ROLES)
def item_detail(item_id: int):
    """Full item details with stock history."""
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("SELECT * FROM inventory_items WHERE item_id = %s", (item_id,))
        item = cursor.fetchone()
        if not item:
            flash("Item not found.", "error")
            return redirect(url_for("inventory.manage_items"))

        cursor.execute("""SELECT t.*, u.first_name, u.last_name
                          FROM inventory_transactions t
                          JOIN users u ON t.created_by = u.user_id
                          WHERE t.inventory_item_id = %s
                          ORDER BY t.created_at DESC
                          LIMIT 20""", (item_id,))
        history = cursor.fetchall() or []

    return render_template(
        "inventory/item_detail.html",
        title=f"{item['item_name']} — Detail",
        active_page="inventory",
        current_user={"username": session.get("username", "User"), "role": session.get("role", "")},
        item=item,
        history=history,
        csrf_token=generate_csrf_token(),
    )


# ══════════════════════════════════════════════════════════════════════
#  EDIT ITEM  /inventory/item/<id>/edit
# ══════════════════════════════════════════════════════════════════════

@inventory_bp.get("/item/<int:item_id>/edit")
@login_required
@role_required(ALLOWED_ROLES)
def edit_item_form(item_id: int):
    """Edit item form."""
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("SELECT * FROM inventory_items WHERE item_id = %s", (item_id,))
        item = cursor.fetchone()
        if not item:
            flash("Item not found.", "error")
            return redirect(url_for("inventory.manage_items"))
        cursor.execute("SELECT * FROM inventory_categories WHERE is_active = TRUE ORDER BY category_name")
        categories = cursor.fetchall() or []
        cursor.execute("SELECT supplier_id, supplier_name FROM suppliers WHERE status = 'Active'")
        suppliers = cursor.fetchall() or []

    return render_template(
        "inventory/edit_item.html",
        title=f"Edit — {item['item_name']}",
        active_page="inventory",
        current_user={"username": session.get("username", "User"), "role": session.get("role", "")},
        item=item,
        categories=categories,
        suppliers=suppliers,
        csrf_token=generate_csrf_token(),
    )


@inventory_bp.post("/item/<int:item_id>/edit")
@login_required
@role_required(ALLOWED_ROLES)
def edit_item_save(item_id: int):
    """Save updated item details."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("inventory.edit_item_form", item_id=item_id))

    data = request.form
    usage_mode = data.get("usage_mode", "Internal")
    is_saleable = 1 if usage_mode in ['Sale', 'Both'] else 0
    track_expiry = 1 if data.get("track_expiry") == "on" else 0

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("""
            UPDATE inventory_items SET
                item_name = %s, item_code = %s, generic_name = %s,
                category = %s, unit = %s,
                minimum_stock_level = %s, max_stock_level = %s,
                buying_price = %s, selling_price = %s,
                usage_mode = %s, is_saleable = %s,
                track_expiry = %s, status = %s,
                storage_location = %s,
                supplier_id = %s,
                updated_at = NOW()
            WHERE item_id = %s
        """, (
            data.get("item_name"), data.get("item_code"), data.get("generic_name"),
            data.get("category"), data.get("unit"),
            data.get("minimum_stock_level", 10), data.get("max_stock_level") or None,
            data.get("buying_price", 0), data.get("selling_price", 0),
            usage_mode, is_saleable,
            track_expiry, data.get("status", "Active"),
            data.get("storage_location") or None,
            data.get("supplier_id") or None,
            item_id
        ))

    flash("Item updated successfully.", "success")
    return redirect(url_for("inventory.item_detail", item_id=item_id))


# ══════════════════════════════════════════════════════════════════════
#  STOCK IN  GET /inventory/stock-in  (page)
#             POST /inventory/stock-in  (submit)
# ══════════════════════════════════════════════════════════════════════

@inventory_bp.get("/stock-in")
@login_required
@role_required(ALLOWED_ROLES)
def stock_in_page():
    """Stock-in page. If ?item_id=X, pre-selects that item."""
    item_id = request.args.get("item_id", type=int)
    selected_item = None

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("""SELECT item_id, item_name, item_code, unit,
                                 quantity_on_hand, buying_price, selling_price, usage_mode
                          FROM inventory_items WHERE status = 'Active'
                          ORDER BY item_name""")
        items = cursor.fetchall() or []

        cursor.execute("SELECT supplier_id, supplier_name FROM suppliers WHERE status = 'Active' ORDER BY supplier_name")
        suppliers = cursor.fetchall() or []

        if item_id:
            cursor.execute("SELECT * FROM inventory_items WHERE item_id = %s", (item_id,))
            selected_item = cursor.fetchone()

    return render_template(
        "inventory/stock_in.html",
        title="Stock In",
        active_page="inventory",
        current_user={"username": session.get("username", "User"), "role": session.get("role", "")},
        items=items,
        suppliers=suppliers,
        selected_item=selected_item,
        csrf_token=generate_csrf_token(),
    )


@inventory_bp.post("/stock-in")
@login_required
@role_required(ALLOWED_ROLES)
def stock_in_submit():
    """Process stock-in form submission."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("inventory.stock_in_page"))

    data = request.form
    item_id = data.get("item_id")
    qty = float(data.get("quantity_received", 0))
    batch = data.get("batch_number") or None
    expiry = data.get("expiry_date") or None
    supplier_id = data.get("supplier_id") or None
    buying_price = float(data.get("buying_price", 0))
    selling_price = data.get("selling_price")
    selling_price = float(selling_price) if selling_price else None
    note = data.get("note") or "New stock received"

    if not item_id or qty <= 0:
        flash("Please select an item and enter a valid quantity.", "error")
        return redirect(url_for("inventory.stock_in_page"))

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        # Build dynamic update — only set selling_price if provided
        update_sql = """
            UPDATE inventory_items
            SET quantity_on_hand = quantity_on_hand + %s,
                batch_number = %s, expiry_date = %s,
                buying_price = %s, supplier_id = %s,
        """
        params = [qty, batch, expiry, buying_price, supplier_id]

        if selling_price is not None:
            update_sql += "selling_price = %s, "
            params.append(selling_price)

        update_sql += "updated_at = NOW() WHERE item_id = %s"
        params.append(item_id)

        cursor.execute(update_sql, tuple(params))

        # Insert into stock_batches for FIFO tracking
        cursor.execute("""
            INSERT INTO stock_batches (
                inventory_item_id, batch_number, quantity_received, quantity_remaining,
                buying_price, selling_price, expiry_date, supplier_id, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            item_id, batch, qty, qty, buying_price, selling_price or 0.00,
            expiry, supplier_id, session.get("user_id")
        ))

        log_inventory_transaction(
            cursor, int(item_id), 'IN', qty, 'Purchase', None, note,
            session.get("user_id"), batch
        )

    flash(f"Successfully stocked in {qty} units.", "success")
    return redirect(url_for("inventory.stock_in_page"))


# ══════════════════════════════════════════════════════════════════════
#  ADJUST STOCK  GET /inventory/adjust  (page)
#                POST /inventory/adjust  (submit)
# ══════════════════════════════════════════════════════════════════════

@inventory_bp.get("/adjust")
@login_required
@role_required(ALLOWED_ROLES)
def adjust_page():
    """Stock adjustment page. If ?item_id=X, pre-selects that item."""
    item_id = request.args.get("item_id", type=int)
    selected_item = None

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("""SELECT item_id, item_name, item_code, unit, quantity_on_hand
                          FROM inventory_items WHERE status = 'Active' ORDER BY item_name""")
        items = cursor.fetchall() or []

        if item_id:
            cursor.execute("SELECT * FROM inventory_items WHERE item_id = %s", (item_id,))
            selected_item = cursor.fetchone()

    return render_template(
        "inventory/adjust_stock.html",
        title="Adjust Stock",
        active_page="inventory",
        current_user={"username": session.get("username", "User"), "role": session.get("role", "")},
        items=items,
        selected_item=selected_item,
        csrf_token=generate_csrf_token(),
    )


@inventory_bp.post("/adjust")
@login_required
@role_required(ALLOWED_ROLES)
def adjust_submit():
    """Process stock adjustment."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("inventory.adjust_page"))

    item_id = request.form.get("item_id")
    adjustment_qty = float(request.form.get("adjustment_qty", 0))
    adjustment_type = request.form.get("adjustment_type", "ADJUST")
    reason = request.form.get("reason") or "Manual adjustment"

    if not item_id:
        flash("Please select an item.", "error")
        return redirect(url_for("inventory.adjust_page"))

    if adjustment_qty == 0:
        flash("Adjustment quantity cannot be zero.", "error")
        return redirect(url_for("inventory.adjust_page", item_id=item_id))

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            "UPDATE inventory_items SET quantity_on_hand = quantity_on_hand + %s, updated_at = NOW() WHERE item_id = %s",
            (adjustment_qty, item_id)
        )
        log_inventory_transaction(
            cursor, int(item_id), adjustment_type, adjustment_qty,
            'Manual', None, reason, session.get("user_id")
        )

    flash("Stock adjusted successfully.", "success")
    return redirect(url_for("inventory.adjust_page"))


# ══════════════════════════════════════════════════════════════════════
#  ALERTS JSON API
# ══════════════════════════════════════════════════════════════════════

@inventory_bp.get("/alerts")
@login_required
def get_alerts():
    """Returns dynamic alerts as JSON."""
    alerts = check_stock_alerts()
    return jsonify(alerts)
