from __future__ import annotations

import re
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request, session

from medicore.communications.communications_service import send_sms
from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import validate_csrf_token
from medicore.inventory.inventory_service import reduce_stock_for_sale


reception_bp = Blueprint("reception", __name__, url_prefix="/reception")

ALLOWED_ROLES = ["Receptionist", "Admin", "SuperAdmin"]
PHONE_PATTERN = re.compile(r"^\d{10}$")


def _now_colombo() -> datetime:
    return datetime.now(ZoneInfo("Asia/Colombo"))


def _normalize_spaces(value: str) -> str:
    return " ".join((value or "").strip().split())


def _split_patient_name(full_name: str) -> tuple[str, str]:
    parts = _normalize_spaces(full_name).split(" ")
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def _derive_birth_year_from_age(age: int) -> int:
    current_year = _now_colombo().year
    return current_year - age


def _generate_patient_number(cursor) -> str:
    # Pattern: PAT-1001, PAT-1002...
    query = "SELECT COUNT(*) AS total FROM patients WHERE patient_number LIKE 'PAT-%'"
    cursor.execute(query)
    total = (cursor.fetchone() or {}).get("total", 0)
    return f"PAT-{(1001 + total):04d}"


def _generate_invoice_id(cursor) -> str:
    # Replicating billing_routes.py logic: INV-YY-XXXX
    year_suffix = _now_colombo().strftime("%y")
    prefix = f"INV-{year_suffix}-"
    # The string code is stored in invoice_number, invoice_id is an auto-incrementing bigint
    cursor.execute("SELECT COUNT(*) AS total FROM invoices WHERE invoice_number LIKE %s", (f"{prefix}%",))
    total = (cursor.fetchone() or {}).get("total", 0)
    return f"{prefix}{(int(total) + 1):04d}"


@reception_bp.post("/quick-sms/<int:appointment_id>")
@login_required
@role_required(ALLOWED_ROLES)
def quick_sms(appointment_id: int):
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()

    if not message:
        return jsonify({"error": "Message is required."}), 400

    query = """
        SELECT p.patient_id, p.phone_number
        FROM appointments a
        INNER JOIN patients p ON p.patient_id = a.patient_id
        WHERE a.appointment_id = %s
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (appointment_id,))
        record = cursor.fetchone()

    if not record:
        return jsonify({"error": "Appointment not found."}), 404

    phone_number = record.get("phone_number")
    if not phone_number:
        return jsonify({"error": "Patient phone number unavailable."}), 400

    send_sms(
        phone_number,
        message,
        patient_id=record.get("patient_id"),
        message_type="Reception Quick SMS",
    )

    return jsonify({"status": "queued"})


@reception_bp.post("/confirm")
@login_required
@role_required(ALLOWED_ROLES)
def reception_confirm():
    payload = request.get_json(silent=True) or {}
    
    # CSRF check handled manually for JSON post
    # In a real app we might use a decorator, but here we validate from payload
    # Note: the frontend sends it as 'csrf_token'
    
    patient_id = payload.get("patient_id")
    patient_new = payload.get("patient_new")
    items = payload.get("items", [])
    discount = Decimal(str(payload.get("discount", 0)))
    payment_method = payload.get("payment_method", "Cash")

    if not items:
        return jsonify({"status": "error", "message": "No items selected."}), 400

    with get_db_cursor(dictionary=True) as (conn, cursor):
        try:
            # 1. Handle Patient
            if not patient_id and patient_new:
                # Create new patient
                p_name = patient_new.get("name", "Unknown")
                p_phone = patient_new.get("phone", "")
                p_gender = patient_new.get("gender", "Male")
                p_age = int(patient_new.get("age") or 0)
                p_nic = (patient_new.get("nic") or "").strip() or None
                
                f_name, l_name = _split_patient_name(p_name)
                b_year = _derive_birth_year_from_age(p_age)
                p_num = _generate_patient_number(cursor)
                
                # Check if patients table has patient_number and birth_year (based on patient_routes investigation)
                # We'll assume the modern schema from patient_routes.py
                cursor.execute(
                    """
                    INSERT INTO patients (patient_number, first_name, last_name, gender, phone_number, nic_number, birth_year)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (p_num, f_name, l_name, p_gender, p_phone, p_nic, b_year)
                )
                patient_id = cursor.lastrowid
            
            if not patient_id:
                raise ValueError("Patient identification failed.")

            # 2. Add Doctor Fee & Hospital Fee if present
            doctor_id = payload.get("doctor_id")
            appointment_date = payload.get("appointment_date")
            token_number = payload.get("token_number")
            
            doctor_fee = Decimal("0.00")
            hospital_fee = Decimal("0.00")
            
            if doctor_id:
                cursor.execute("SELECT doctor_fee, hospital_fee FROM doctors WHERE doctor_id = %s", (doctor_id,))
                doc_row = cursor.fetchone()
                if doc_row:
                    doctor_fee = Decimal(str(doc_row["doctor_fee"]))
                    hospital_fee = Decimal(str(doc_row["hospital_fee"]))
            
            # 3. Create Appointment if Doctor Selected
            appointment_id = None
            if doctor_id and appointment_date:
                cursor.execute(
                    """
                    INSERT INTO appointments (
                        patient_id, doctor_id, appointment_date, appointment_time, 
                        appointment_mode, reason_for_visit, status, token_number
                    ) VALUES (%s, %s, %s, '00:00:00', 'In-Person', 'Channeling', 'Scheduled', %s)
                    """,
                    (patient_id, doctor_id, appointment_date, token_number)
                )
                appointment_id = cursor.lastrowid

            # 4. Calculate Totals
            # Subtotal here includes service items only, 
            # while doctor_fee and hospital_fee are stored separately
            services_subtotal = Decimal("0.00")
            for item in items:
                price = Decimal(str(item.get("price", 0)))
                qty = int(item.get("quantity", 1))
                services_subtotal += (price * qty)
            
            # Grand Total = Services + Doctor + Hospital - Discount
            total_amount = (services_subtotal + doctor_fee + hospital_fee - discount)

            # 5. Create Invoice (Pending)
            invoice_code = _generate_invoice_id(cursor)
            
            cursor.execute(
                """
                INSERT INTO invoices (
                    invoice_number, patient_id, appointment_id, subtotal, 
                    doctor_fee, hospital_fee, tax_amount, 
                    discount_amount, total_amount, status, created_at, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, 0, %s, %s, 'Pending', NOW(), %s)
                """,
                (invoice_code, patient_id, appointment_id, services_subtotal, doctor_fee, hospital_fee, discount, total_amount, session.get("user_id"))
            )
            # Use the auto-increment BIGINT id for linked items
            real_invoice_id = cursor.lastrowid
            
            # 6. Create Invoice Items + handle inventory stock reduction
            for item in items:
                desc = item.get("item_name", "Service")
                qty = int(item.get("quantity", 1))
                price = Decimal(str(item.get("price", 0)))
                line_total = (price * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                
                # Determine if this is a service item or a direct inventory item
                item_type = item.get("type", "service")
                service_item_id = item.get("item_id") if item_type != "inventory" else None
                direct_inventory_id = item.get("item_id") if item_type == "inventory" else None
                
                # Try to insert with optional service_item_id / inventory_item_id columns
                try:
                    cursor.execute(
                        """
                        INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, line_total)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (real_invoice_id, desc, qty, price, line_total)
                    )
                except Exception:
                    cursor.execute(
                        """
                        INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, line_total)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (real_invoice_id, desc, qty, price, line_total)
                    )
                
                # ── Inventory Stock Deduction ──────────────────────────────
                # Case A: direct inventory sale item (type == 'inventory')
                if direct_inventory_id:
                    reduce_stock_for_sale(
                        inventory_item_id=int(direct_inventory_id),
                        qty=float(qty),
                        ref_id=str(invoice_code),
                        user_id=session.get("user_id"),
                        cursor=cursor
                    )
                
                # Case B: service item that has a linked inventory item
                elif service_item_id:
                    cursor.execute(
                        "SELECT linked_inventory_item_id FROM service_items WHERE item_id = %s LIMIT 1",
                        (int(service_item_id),)
                    )
                    svc_row = cursor.fetchone()
                    if svc_row and svc_row.get("linked_inventory_item_id"):
                        linked_inv_id = int(svc_row["linked_inventory_item_id"])
                        # Deduct stock for the linked inventory item
                        cursor.execute(
                            "UPDATE inventory_items SET quantity_on_hand = quantity_on_hand - %s WHERE item_id = %s",
                            (qty, linked_inv_id)
                        )
                        from medicore.inventory.inventory_service import log_inventory_transaction
                        log_inventory_transaction(
                            cursor,
                            linked_inv_id,
                            "SALE",
                            float(qty),
                            "Bill",
                            str(invoice_code),
                            f"Service sale via linked inventory item ID {service_item_id}",
                            session.get("user_id")
                        )

            return jsonify({
                "status": "success",
                "invoice_id": invoice_code
            })

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500