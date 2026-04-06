from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, flash, redirect, render_template, request, session, url_for, current_app, jsonify

from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token
from medicore.utils.timezone import get_colombo_time

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")

ALLOWED_ROLES = ["Receptionist", "Admin", "SuperAdmin"]
PAYMENT_METHODS = ["Cash", "Card", "Bank Transfer"]


def _now_colombo() -> datetime:
    return get_colombo_time()


def _format_lkr(amount: Decimal | float | str) -> str:
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"LKR {value:,.2f}"


def _load_tax_rules() -> list[dict]:
    query = """
        SELECT tax_id, tax_name, percentage, is_active
        FROM tax_rules
        WHERE is_active = 1
        ORDER BY tax_id ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _get_tax_rate() -> Decimal:
    return Decimal(str(current_app.config.get("BILLING_TAX_RATE", "0.18")))


def _calculate_taxes(subtotal: Decimal, tax_rules: list[dict]) -> tuple[Decimal, dict]:
    sscl_rate = Decimal("0.00")
    vat_rate = Decimal("0.00")
    other_rates: list[Decimal] = []

    for rule in tax_rules:
        name = (rule.get("tax_name") or "").strip().upper()
        rate = Decimal(str(rule.get("percentage") or 0)) / Decimal("100")
        if name == "SSCL":
            sscl_rate = rate
        elif name == "VAT":
            vat_rate = rate
        else:
            other_rates.append(rate)

    sscl_amount = (subtotal * sscl_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    vat_base = (subtotal + sscl_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    vat_amount = (vat_base * vat_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    other_amount = Decimal("0.00")
    for rate in other_rates:
        other_amount += (subtotal * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total_tax = (sscl_amount + vat_amount + other_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return total_tax, {
        "sscl_rate": sscl_rate,
        "vat_rate": vat_rate,
        "sscl_amount": sscl_amount,
        "vat_amount": vat_amount,
        "other_amount": other_amount,
    }


def _parse_decimal(value: str | None, default: str = "0.00") -> Decimal:
    try:
        return Decimal(value or default)
    except Exception:
        return Decimal(default)


def _generate_invoice_id(conn, cursor) -> str:
    year_suffix = _now_colombo().strftime("%y")
    prefix = f"INV-{year_suffix}-"
    cursor.execute("SELECT COUNT(*) AS total FROM invoices WHERE invoice_number LIKE %s", (f"{prefix}%",))
    total = (cursor.fetchone() or {}).get("total", 0)
    sequence = int(total) + 1
    return f"{prefix}{sequence:04d}"


def _load_patients():
    query = """
        SELECT patient_id, first_name, last_name, nic_number
        FROM patients
        ORDER BY last_name, first_name
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _load_invoice(invoice_number_str: str):
    # Lookup the integer ID first
    id_query = "SELECT invoice_id FROM invoices WHERE invoice_number = %s"
    invoice_query = """
        SELECT i.*, CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
               p.nic_number, p.phone_number
        FROM invoices i
        INNER JOIN patients p ON p.patient_id = i.patient_id
        WHERE i.invoice_id = %s
    """
    items_query = """
        SELECT description, quantity, unit_price, line_total
        FROM invoice_items
        WHERE invoice_id = %s
        ORDER BY item_id ASC
    """
    payments_query = """
        SELECT amount_paid, payment_method, transaction_reference, payment_date
        FROM payments
        WHERE invoice_id = %s
        ORDER BY payment_date DESC
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(id_query, (invoice_number_str,))
        row = cursor.fetchone()
        if not row:
            return None
        real_id = row["invoice_id"]
        
        cursor.execute(invoice_query, (real_id,))
        invoice = cursor.fetchone()
        if not invoice:
            return None
            
        cursor.execute(items_query, (real_id,))
        items = cursor.fetchall() or []
        cursor.execute(payments_query, (real_id,))
        payments = cursor.fetchall() or []

    return invoice, items, payments


@billing_bp.get("")
@login_required
@role_required(ALLOWED_ROLES)
def billing_dashboard():
    # This now serves as the Billing Workstation entry point
    return render_template(
        "billing/billing_workstation.html",
        title="Billing Workstation",
        active_page="billing",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        csrf_token=generate_csrf_token(),
    )


@billing_bp.get("/api/pending")
@login_required
@role_required(ALLOWED_ROLES)
def billing_api_pending():
    query = """
        SELECT i.invoice_id, i.invoice_number, i.patient_id, i.total_amount, i.status, i.created_at,
               CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
               p.phone_number, a.token_number, d.doctor_name
        FROM invoices i
        INNER JOIN patients p ON p.patient_id = i.patient_id
        LEFT JOIN appointments a ON a.appointment_id = i.appointment_id
        LEFT JOIN doctors d ON d.doctor_id = a.doctor_id
        WHERE i.status IN ('Pending', 'Partial')
        ORDER BY i.created_at DESC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        rows = cursor.fetchall() or []
    
    return jsonify({"ok": True, "bills": rows})


@billing_bp.get("/api/invoice/<invoice_id>")
@login_required
@role_required(ALLOWED_ROLES)
def billing_api_invoice(invoice_id: str):
    data = _load_invoice(invoice_id)
    if not data:
        return jsonify({"ok": False, "message": "Invoice not found"}), 404
        
    invoice, items, payments = data
    total_paid = sum((p["amount_paid"] for p in payments), Decimal("0.00"))
    
    # Add doctor info if available via appointment
    if invoice.get("appointment_id"):
        with get_db_cursor(dictionary=True) as (_conn, cursor):
            cursor.execute(
                """
                SELECT a.token_number, a.appointment_date, d.doctor_name
                FROM appointments a
                LEFT JOIN doctors d ON d.doctor_id = a.doctor_id
                WHERE a.appointment_id = %s
                """,
                (invoice["appointment_id"],)
            )
            appt = cursor.fetchone()
            if appt:
                invoice.update(appt)

    return jsonify({
        "ok": True,
        "invoice": invoice,
        "items": items,
        "payments": payments,
        "total_paid": str(total_paid),
        "balance": str(invoice["total_amount"] - total_paid)
    })


@billing_bp.post("/api/pay/<invoice_id>")
@login_required
@role_required(ALLOWED_ROLES)
def billing_api_pay(invoice_id: str):
    payload = request.get_json(silent=True) or {}
    amount_paid = _parse_decimal(str(payload.get("amount", 0)))
    payment_method = payload.get("method", "Cash")
    
    if amount_paid <= 0:
        return jsonify({"ok": False, "message": "Amount must be > 0"}), 400

    insert_payment = """
        INSERT INTO payments (invoice_id, amount_paid, payment_method, payment_date)
        VALUES (%s, %s, %s, NOW())
    """
    
    # Lookup bigint ID for internal payment linking
    with get_db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT invoice_id FROM invoices WHERE invoice_number = %s", (invoice_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"ok": False, "message": "Invoice not found"}), 404
        real_id = row["invoice_id"]

        cursor.execute(insert_payment, (real_id, amount_paid, payment_method))
        
        # Recalculate status
        cursor.execute("SELECT total_amount FROM invoices WHERE invoice_id = %s", (real_id,))
        inv = cursor.fetchone()
        cursor.execute("SELECT SUM(amount_paid) AS total_paid FROM payments WHERE invoice_id = %s", (real_id,))
        paid = cursor.fetchone()
        
        total = Decimal(str(inv["total_amount"]))
        total_paid = Decimal(str(paid["total_paid"] or 0))
        
        new_status = "Paid" if total_paid >= total else "Partial"
        cursor.execute("UPDATE invoices SET status = %s WHERE invoice_id = %s", (new_status, real_id))

    return jsonify({"ok": True, "status": new_status})


@billing_bp.get("/create/<patient_id>")
@login_required
@role_required(ALLOWED_ROLES)
def billing_create(patient_id: str):
    patients = _load_patients()
    tax_rules = _load_tax_rules()
    return render_template(
        "billing/invoice_create.html",
        title="Create Invoice",
        active_page="billing",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        patients=patients,
        selected_patient_id=patient_id,
        tax_rate=_get_tax_rate(),
        tax_rules=tax_rules,
        csrf_token=generate_csrf_token(),
    )


@billing_bp.post("/create")
@login_required
@role_required(ALLOWED_ROLES)
def billing_create_submit():
    if not validate_csrf_token():
        flash("Invalid request token. Please retry.", "error")
        return redirect(url_for("billing.billing_dashboard"))

    patient_id = request.form.get("patient_id")
    appointment_id = request.form.get("appointment_id") or None
    discount_amount = _parse_decimal(request.form.get("discount_amount"))

    descriptions = request.form.getlist("item_description")
    quantities = request.form.getlist("item_quantity")
    unit_prices = request.form.getlist("item_unit_price")

    if not patient_id or not descriptions:
        flash("Please select a patient and add at least one line item.", "error")
        return redirect(url_for("billing.billing_dashboard"))

    line_items = []
    subtotal = Decimal("0.00")
    for idx, description in enumerate(descriptions):
        description = (description or "").strip()
        if not description:
            continue
        try:
            quantity = int(quantities[idx]) if idx < len(quantities) else 1
        except (ValueError, TypeError):
            quantity = 1
        quantity = max(quantity, 1)
        unit_price = _parse_decimal(unit_prices[idx] if idx < len(unit_prices) else "0.00")
        line_total = (unit_price * Decimal(quantity)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal += line_total
        line_items.append((description, quantity, unit_price, line_total))

    if not line_items:
        flash("At least one valid line item is required.", "error")
        return redirect(url_for("billing.billing_dashboard"))

    tax_rules = _load_tax_rules()
    if tax_rules:
        tax_amount, _tax_breakdown = _calculate_taxes(subtotal, tax_rules)
    else:
        tax_rate = _get_tax_rate()
        tax_amount = (subtotal * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    discount_amount = max(discount_amount, Decimal("0.00"))
    total_amount = (subtotal + tax_amount - discount_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if total_amount < 0:
        flash("Discount cannot exceed total amount.", "error")
        return redirect(url_for("billing.billing_dashboard"))

    invoice_insert = """
        INSERT INTO invoices (
            invoice_number, patient_id, appointment_id, subtotal, tax_amount,
            discount_amount, total_amount, status, created_at, created_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending', NOW(), %s)
    """
    item_insert = """
        INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, line_total)
        VALUES (%s, %s, %s, %s, %s)
    """

    with get_db_cursor(dictionary=True) as (conn, cursor):
        invoice_code = _generate_invoice_id(conn, cursor)
        cursor.execute(
            invoice_insert,
            (
                invoice_code,
                patient_id,
                appointment_id,
                subtotal,
                tax_amount,
                discount_amount,
                total_amount,
                session.get("user_id"),
            ),
        )
        real_invoice_id = cursor.lastrowid
        for description, quantity, unit_price, line_total in line_items:
            cursor.execute(item_insert, (real_invoice_id, description, quantity, unit_price, line_total))

    flash(f"Invoice {invoice_code} created successfully.", "success")
    return redirect(url_for("billing.invoice_view", invoice_id=invoice_code))


@billing_bp.get("/invoice/<invoice_id>")
@login_required
@role_required(ALLOWED_ROLES)
def invoice_view(invoice_id: str):
    data = _load_invoice(invoice_id)
    if not data:
        flash("Invoice not found.", "error")
        return redirect(url_for("billing.billing_dashboard"))

    invoice, items, payments = data
    total_paid = sum((payment["amount_paid"] for payment in payments), Decimal("0.00"))

    return render_template(
        "billing/invoice_view.html",
        title=f"Invoice {invoice_id}",
        active_page="billing",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        invoice=invoice,
        items=items,
        payments=payments,
        total_paid=total_paid,
        format_lkr=_format_lkr,
        payment_methods=PAYMENT_METHODS,
        csrf_token=generate_csrf_token(),
    )


@billing_bp.post("/pay/<invoice_id>")
@login_required
@role_required(ALLOWED_ROLES)
def invoice_pay(invoice_id: str):
    if not validate_csrf_token():
        flash("Invalid request token. Please retry.", "error")
        return redirect(url_for("billing.invoice_view", invoice_id=invoice_id))

    amount_paid = _parse_decimal(request.form.get("amount_paid"))
    payment_method = request.form.get("payment_method")
    transaction_reference = (request.form.get("transaction_reference") or "").strip() or None

    if amount_paid <= 0:
        flash("Payment amount must be greater than zero.", "error")
        return redirect(url_for("billing.invoice_view", invoice_id=invoice_id))

    if payment_method not in PAYMENT_METHODS:
        flash("Invalid payment method.", "error")
        return redirect(url_for("billing.invoice_view", invoice_id=invoice_id))

    insert_payment = """
        INSERT INTO payments (invoice_id, amount_paid, payment_method, transaction_reference, payment_date)
        VALUES (%s, %s, %s, %s, NOW())
    """

    total_query = """
        SELECT total_amount,
               (SELECT COALESCE(SUM(amount_paid), 0) FROM payments WHERE invoice_id = %s) AS total_paid
        FROM invoices
        WHERE invoice_id = %s
    """

    update_status = """
        UPDATE invoices
        SET status = %s
        WHERE invoice_id = %s
    """

    with get_db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(insert_payment, (invoice_id, amount_paid, payment_method, transaction_reference))
        cursor.execute(total_query, (invoice_id, invoice_id))
        totals = cursor.fetchone()
        if not totals:
            raise ValueError("Invoice not found for payment update")

        total_amount = Decimal(str(totals["total_amount"]))
        total_paid = Decimal(str(totals["total_paid"]))
        new_status = "Partial"
        if total_paid >= total_amount:
            new_status = "Paid"
        cursor.execute(update_status, (new_status, invoice_id))

    flash("Payment recorded successfully.", "success")
    return redirect(url_for("billing.invoice_view", invoice_id=invoice_id))
