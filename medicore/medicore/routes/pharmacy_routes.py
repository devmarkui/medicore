from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token

pharmacy_bp = Blueprint("pharmacy", __name__, url_prefix="/pharmacy")

ALLOWED_ROLES = ["Pharmacist", "Admin", "SuperAdmin"]
PAYMENT_METHODS = ["Cash", "Card"]
LOW_STOCK_THRESHOLD = 10
EXPIRY_WARNING_DAYS = 30


def _now_colombo() -> datetime:
    return datetime.now(ZoneInfo("Asia/Colombo"))


def _format_lkr(amount: Decimal | float | str) -> str:
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"LKR {value:,.2f}"


def _parse_decimal(value: str | None, default: str = "0.00") -> Decimal:
    try:
        return Decimal(value or default)
    except Exception:
        return Decimal(default)


def _load_inventory_summary():
    low_stock_query = """
        SELECT d.drug_id, d.generic_name, d.brand_name,
               SUM(b.quantity_in_stock) AS total_stock
        FROM drugs_master d
        INNER JOIN inventory_batches b ON b.drug_id = d.drug_id
        GROUP BY d.drug_id
        HAVING total_stock < %s
        ORDER BY total_stock ASC
        LIMIT 20
    """

    expiring_query = """
        SELECT b.batch_id, d.generic_name, d.brand_name, b.batch_number, b.expiry_date, b.quantity_in_stock
        FROM inventory_batches b
        INNER JOIN drugs_master d ON d.drug_id = b.drug_id
        WHERE b.expiry_date <= %s AND b.quantity_in_stock > 0
        ORDER BY b.expiry_date ASC
        LIMIT 20
    """

    expiry_cutoff = (_now_colombo().date() + timedelta(days=EXPIRY_WARNING_DAYS))

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(low_stock_query, (LOW_STOCK_THRESHOLD,))
        low_stock = cursor.fetchall() or []
        cursor.execute(expiring_query, (expiry_cutoff,))
        expiring = cursor.fetchall() or []

    return low_stock, expiring


def _load_inventory_batches():
    query = """
        SELECT b.batch_id, d.generic_name, d.brand_name, d.form, d.strength,
               b.batch_number, b.manufacturing_date, b.expiry_date, b.quantity_in_stock,
               b.purchase_price_lkr, b.selling_price_lkr, b.supplier_details
        FROM inventory_batches b
        INNER JOIN drugs_master d ON d.drug_id = b.drug_id
        ORDER BY b.expiry_date ASC
        LIMIT 200
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _load_prescription(prescription_id: str):
    prescription_query = """
        SELECT p.prescription_id, p.patient_id, p.status,
               CONCAT(pt.first_name, ' ', pt.last_name) AS patient_name
        FROM prescriptions p
        INNER JOIN patients pt ON pt.patient_id = p.patient_id
        WHERE p.prescription_id = %s
        LIMIT 1
    """
    items_query = """
        SELECT i.drug_id, i.dosage, i.frequency, i.duration_days, i.special_instructions,
               d.generic_name, d.brand_name, d.form, d.strength,
               COALESCE(SUM(b.quantity_in_stock), 0) AS available_stock,
               MIN(b.selling_price_lkr) AS selling_price
        FROM prescription_items i
        INNER JOIN drugs_master d ON d.drug_id = i.drug_id
        LEFT JOIN inventory_batches b ON b.drug_id = i.drug_id AND b.quantity_in_stock > 0
        WHERE i.prescription_id = %s
        GROUP BY i.item_id, i.drug_id
        ORDER BY i.item_id ASC
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(prescription_query, (prescription_id,))
        prescription = cursor.fetchone()
        if not prescription:
            return None
        cursor.execute(items_query, (prescription_id,))
        items = cursor.fetchall() or []

    return prescription, items


@pharmacy_bp.get("/dashboard")
@login_required
@role_required(ALLOWED_ROLES)
def pharmacy_dashboard():
    low_stock, expiring = _load_inventory_summary()

    return render_template(
        "pharmacy/pharmacy_dashboard.html",
        title="Pharmacy",
        active_page="pharmacy",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        low_stock=low_stock,
        expiring=expiring,
        expiry_days=EXPIRY_WARNING_DAYS,
        csrf_token=generate_csrf_token(),
    )


@pharmacy_bp.get("/inventory")
@login_required
@role_required(ALLOWED_ROLES)
def inventory_management():
    batches = _load_inventory_batches()
    return render_template(
        "pharmacy/inventory_management.html",
        title="Inventory",
        active_page="pharmacy",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        batches=batches,
        csrf_token=generate_csrf_token(),
    )


@pharmacy_bp.post("/inventory/add")
@login_required
@role_required(ALLOWED_ROLES)
def inventory_add_batch():
    if not request.form.get("drug_id"):
        flash("Drug is required.", "error")
        return redirect(url_for("pharmacy.inventory_management"))

    insert_query = """
        INSERT INTO inventory_batches (
            drug_id, batch_number, manufacturing_date, expiry_date, quantity_in_stock,
            purchase_price_lkr, selling_price_lkr, supplier_details
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            insert_query,
            (
                request.form.get("drug_id"),
                request.form.get("batch_number"),
                request.form.get("manufacturing_date"),
                request.form.get("expiry_date"),
                int(request.form.get("quantity_in_stock") or 0),
                _parse_decimal(request.form.get("purchase_price_lkr")),
                _parse_decimal(request.form.get("selling_price_lkr")),
                request.form.get("supplier_details"),
            ),
        )

    flash("Inventory batch added.", "success")
    return redirect(url_for("pharmacy.inventory_management"))


@pharmacy_bp.get("/pos")
@login_required
@role_required(ALLOWED_ROLES)
def pharmacy_pos():
    return render_template(
        "pharmacy/pharmacy_pos.html",
        title="Pharmacy POS",
        active_page="pharmacy",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        prescription=None,
        prescription_items=[],
        payment_methods=PAYMENT_METHODS,
        csrf_token=generate_csrf_token(),
    )


@pharmacy_bp.get("/prescription/<prescription_id>")
@login_required
@role_required(ALLOWED_ROLES)
def pharmacy_prescription(prescription_id: str):
    data = _load_prescription(prescription_id)
    if not data:
        flash("Prescription not found.", "error")
        return redirect(url_for("pharmacy.pharmacy_pos"))

    prescription, items = data
    return render_template(
        "pharmacy/pharmacy_pos.html",
        title="Pharmacy POS",
        active_page="pharmacy",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        prescription=prescription,
        prescription_items=items,
        payment_methods=PAYMENT_METHODS,
        csrf_token=generate_csrf_token(),
    )


@pharmacy_bp.get("/api/inventory-search")
@login_required
@role_required(ALLOWED_ROLES)
def inventory_search():
    query_text = (request.args.get("q") or "").strip()
    if not query_text:
        return jsonify([])

    like_term = f"%{query_text}%"
    query = """
        SELECT d.drug_id, d.generic_name, d.brand_name, d.form, d.strength,
               SUM(b.quantity_in_stock) AS total_stock,
               MIN(b.selling_price_lkr) AS selling_price
        FROM drugs_master d
        INNER JOIN inventory_batches b ON b.drug_id = d.drug_id
        WHERE (d.generic_name LIKE %s OR d.brand_name LIKE %s)
          AND b.quantity_in_stock > 0
        GROUP BY d.drug_id
        ORDER BY d.generic_name ASC
        LIMIT 20
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (like_term, like_term))
        results = cursor.fetchall() or []

    return jsonify(results)


@pharmacy_bp.post("/checkout")
@login_required
@role_required(ALLOWED_ROLES)
def pharmacy_checkout():
    payload = request.get_json(silent=True) or {}
    if payload.get("csrf_token") != session.get("csrf_token"):
        return jsonify({"error": "Invalid CSRF token"}), 400

    items = payload.get("items") or []
    if not items:
        return jsonify({"error": "No items in cart"}), 400

    payment_method = payload.get("payment_method")
    if payment_method not in PAYMENT_METHODS:
        return jsonify({"error": "Invalid payment method"}), 400

    patient_id = payload.get("patient_id")
    prescription_id = payload.get("prescription_id")

    sale_insert = """
        INSERT INTO pharmacy_sales (patient_id, prescription_id, total_amount, payment_method, sale_date, sold_by)
        VALUES (%s, %s, %s, %s, NOW(), %s)
    """
    sale_item_insert = """
        INSERT INTO pharmacy_sale_items (sale_id, batch_id, quantity, unit_price, subtotal)
        VALUES (%s, %s, %s, %s, %s)
    """

    with get_db_cursor(dictionary=True) as (conn, cursor):
        conn.start_transaction()

        sale_total = Decimal("0.00")
        sale_items = []

        for item in items:
            drug_id = item.get("drug_id")
            quantity_needed = int(item.get("quantity") or 0)
            if not drug_id or quantity_needed <= 0:
                raise ValueError("Invalid cart item")

            batch_query = """
                SELECT batch_id, quantity_in_stock, selling_price_lkr
                FROM inventory_batches
                WHERE drug_id = %s AND quantity_in_stock > 0
                ORDER BY expiry_date ASC, manufacturing_date ASC
                FOR UPDATE
            """
            cursor.execute(batch_query, (drug_id,))
            batches = cursor.fetchall() or []

            remaining = quantity_needed
            for batch in batches:
                if remaining <= 0:
                    break
                available = int(batch["quantity_in_stock"])
                if available <= 0:
                    continue
                take_qty = min(available, remaining)
                unit_price = Decimal(str(batch["selling_price_lkr"]))
                line_total = (unit_price * Decimal(take_qty)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                sale_items.append((batch["batch_id"], take_qty, unit_price, line_total))
                sale_total += line_total
                remaining -= take_qty

            if remaining > 0:
                conn.rollback()
                return jsonify({"error": "Insufficient stock for selected drug."}), 400

        cursor.execute(
            sale_insert,
            (
                patient_id,
                prescription_id,
                sale_total,
                payment_method,
                session.get("user_id"),
            ),
        )
        sale_id = cursor.lastrowid

        update_stock = """
            UPDATE inventory_batches
            SET quantity_in_stock = quantity_in_stock - %s
            WHERE batch_id = %s
        """

        for batch_id, qty, unit_price, subtotal in sale_items:
            cursor.execute(sale_item_insert, (sale_id, batch_id, qty, unit_price, subtotal))
            cursor.execute(update_stock, (qty, batch_id))

        if prescription_id:
            cursor.execute("UPDATE prescriptions SET status = 'Dispensed' WHERE prescription_id = %s", (prescription_id,))

    return jsonify({
        "sale_id": sale_id,
        "total_amount": str(sale_total),
        "message": "Sale completed successfully"
    })
