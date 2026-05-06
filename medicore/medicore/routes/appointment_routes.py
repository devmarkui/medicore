from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token
from medicore.communications.communications_service import send_sms
from medicore.inventory.inventory_service import reduce_stock_for_service

appointments_bp = Blueprint("appointments", __name__, url_prefix="/appointments")

STATUS_OPTIONS = ["Scheduled", "Checked-In", "Completed", "Cancelled"]
RECEPTION_ROLES = ["Receptionist", "Admin", "SuperAdmin"]
DOCTOR_ROLES = ["Doctor", "SuperAdmin"]
PAYMENT_METHODS = ["Cash", "Card"]
PHONE_PATTERN = re.compile(r"^\d{10}$")
NAME_PATTERN = re.compile(r"^[A-Za-z ]{2,}$")
NIC_PATTERN = re.compile(r"^(\d{9}[VvXx]|\d{12})$")


def _today_colombo() -> date:
    return datetime.now(ZoneInfo("Asia/Colombo")).date()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _format_time(value) -> str:
    if value is None:
        return ""
    if isinstance(value, timedelta):
        return (datetime.min + value).strftime("%H:%M")
    if isinstance(value, (datetime, time)):
        return value.strftime("%H:%M")
    return str(value)[:5]


def _load_doctors() -> list[dict]:
    query = """
        SELECT doctor_id AS id,
               doctor_name,
               doctor_fee,
               hospital_fee
        FROM doctors
        WHERE is_active = 1
        ORDER BY doctor_name ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _load_patients(limit: int = 200) -> list[dict]:
    query = """
        SELECT patient_id, first_name, last_name, nic_number
        FROM patients
        ORDER BY last_name, first_name
        LIMIT %s
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (limit,))
        return cursor.fetchall() or []


def _build_time_slots(start_hour: int = 8, end_hour: int = 17, interval_minutes: int = 30) -> list[str]:
    slots = []
    start_time = time(hour=start_hour, minute=0)
    end_time = time(hour=end_hour, minute=0)
    current = datetime.combine(date.today(), start_time)
    end = datetime.combine(date.today(), end_time)
    while current <= end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=interval_minutes)
    return slots


def _normalize_spaces(value: str) -> str:
    return " ".join((value or "").strip().split())


def _split_patient_name(full_name: str) -> tuple[str, str]:
    parts = _normalize_spaces(full_name).split(" ")
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def _parse_money(value: str | None, default: str = "0.00") -> Decimal:
    try:
        return Decimal(value or default).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal(default).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _derive_birth_year_from_age(age: int) -> int:
    return _today_colombo().year - age


def _format_token_for_display(value: int | None) -> str:
    if value is None:
        return "Not started"
    return f"{int(value):02d}"


def _calculate_age(dob, birth_year) -> int | None:
    if dob:
        today = _today_colombo()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if birth_year:
        return max(0, _today_colombo().year - int(birth_year))
    return None


def _patients_has_column(column_name: str) -> bool:
    query = """
        SELECT COUNT(*) AS total
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'patients'
          AND column_name = %s
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (column_name,))
        row = cursor.fetchone() or {}
    return int(row.get("total", 0)) > 0


def _appointments_has_column(column_name: str) -> bool:
    query = """
        SELECT COUNT(*) AS total
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = 'appointments'
          AND column_name = %s
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (column_name,))
        row = cursor.fetchone() or {}
    return int(row.get("total", 0)) > 0


def _generate_patient_number(cursor) -> str:
    query = """
        SELECT MAX(CAST(SUBSTRING(patient_number, 5) AS UNSIGNED)) AS max_num
        FROM patients
        WHERE patient_number LIKE 'PAT-%'
    """
    cursor.execute(query)
    row = cursor.fetchone() or {}
    max_num = row.get("max_num")
    next_num = 1001 if not max_num else int(max_num) + 1
    return f"PAT-{next_num:04d}"


def _generate_invoice_number(cursor) -> str:
    year_suffix = datetime.now(ZoneInfo("Asia/Colombo")).strftime("%y")
    prefix = f"INV-{year_suffix}-"
    cursor.execute("SELECT COUNT(*) AS total FROM invoices WHERE invoice_number LIKE %s", (f"{prefix}%",))
    row = cursor.fetchone() or {}
    sequence = int(row.get("total", 0)) + 1
    return f"{prefix}{sequence:04d}"


def _load_doctor_channeling_meta(doctor_id: int, booking_date: date) -> dict:
    ongoing_query = """
        SELECT queue_number
        FROM physical_queues
        WHERE doctor_id = %s
          AND queue_date = %s
          AND status = 'In Consultation'
        ORDER BY queue_number DESC
        LIMIT 1
    """
    has_token_number = _appointments_has_column("token_number")
    paid_token_query = """
        SELECT COALESCE(MAX(a.token_number), 0) AS max_token
        FROM appointments a
        INNER JOIN invoices i ON i.appointment_id = a.appointment_id
        WHERE a.doctor_id = %s
          AND a.appointment_date = %s
          AND a.status != 'Cancelled'
          AND i.status = 'Paid'
          AND a.token_number IS NOT NULL
    """
    fallback_token_query = """
        SELECT COALESCE(MAX(queue_number), 0) AS max_queue
        FROM physical_queues
        WHERE doctor_id = %s
          AND queue_date = %s
    """
    fee_query = """
        SELECT doctor_fee, hospital_fee
        FROM doctors
        WHERE doctor_id = %s
          AND is_active = 1
        LIMIT 1
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(ongoing_query, (doctor_id, booking_date))
        ongoing = cursor.fetchone()
        max_paid_token = 0
        if has_token_number:
            cursor.execute(paid_token_query, (doctor_id, booking_date))
            paid_row = cursor.fetchone() or {}
            max_paid_token = int(paid_row.get("max_token") or 0)

        cursor.execute(fallback_token_query, (doctor_id, booking_date))
        max_queue = cursor.fetchone() or {}
        cursor.execute(fee_query, (doctor_id,))
        fee_row = cursor.fetchone() or {}

    ongoing_token = ongoing.get("queue_number") if ongoing else None
    fallback_max = int(max_queue.get("max_queue") or 0)
    next_token = (max(max_paid_token, fallback_max) if has_token_number else fallback_max) + 1

    doctor_fee = Decimal(str(fee_row.get("doctor_fee") or "0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    hospital_fee = Decimal(str(fee_row.get("hospital_fee") or "0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = (doctor_fee + hospital_fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "ongoing_token": _format_token_for_display(ongoing_token),
        "next_token": _format_token_for_display(next_token),
        "doctor_fee": f"{doctor_fee:.2f}",
        "hospital_fee": f"{hospital_fee:.2f}",
        "total_amount": f"{total:.2f}",
    }


@appointments_bp.get("/api/doctors")
@login_required
def doctors_api():
    active_only = (request.args.get("active") or "").lower() == "true"
    doctors = _load_doctors()
    if not active_only:
        query = """
            SELECT doctor_id AS id, doctor_name, doctor_fee, hospital_fee, is_active
            FROM doctors
            ORDER BY doctor_name ASC
        """
        with get_db_cursor(dictionary=True) as (_conn, cursor):
            cursor.execute(query)
            doctors = cursor.fetchall() or []
    return jsonify({"ok": True, "doctors": doctors})


def _patient_lookup_by_phone(phone_digits: str) -> list[dict]:
    has_birth_year = _patients_has_column("birth_year")
    birth_year_select = "birth_year" if has_birth_year else "NULL AS birth_year"
    has_patient_number = _patients_has_column("patient_number")
    display_id = "patient_number" if has_patient_number else "patient_id"

    query = f"""
        SELECT patient_id,
               {display_id} AS display_patient_id,
               first_name,
               last_name,
               nic_number,
               gender,
               date_of_birth,
               {birth_year_select}
        FROM patients
        WHERE phone_number LIKE %s
        ORDER BY first_name ASC, last_name ASC, patient_id ASC
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (f"%{phone_digits}%",))
        rows = cursor.fetchall() or []

    payload = []
    for row in rows:
        full_name = f"{(row.get('first_name') or '').strip()} {(row.get('last_name') or '').strip()}".strip()
        payload.append(
            {
                "patient_id": row.get("patient_id"),
                "display_patient_id": row.get("display_patient_id") or row.get("patient_id"),
                "patient_name": full_name,
                "nic": row.get("nic_number") or "",
                "gender": row.get("gender") or "",
                "age": _calculate_age(row.get("date_of_birth"), row.get("birth_year")),
            }
        )

    return payload


@appointments_bp.get("")
@login_required
@role_required(RECEPTION_ROLES)
def appointments_dashboard():
    selected_date = _parse_date(request.args.get("date")) or _today_colombo()
    selected_doctor = request.args.get("doctor_id")

    query = """
     SELECT a.appointment_id, a.patient_id, a.doctor_id, a.appointment_date,
         a.appointment_time, a.status, a.reason_for_visit,
         a.appointment_mode, a.telehealth_link,
         CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
         COALESCE(d.doctor_name, u.full_name, u.email) AS doctor_name
        FROM appointments a
        INNER JOIN patients p ON p.patient_id = a.patient_id
     LEFT JOIN doctors d ON d.doctor_id = a.doctor_id
     LEFT JOIN users u ON u.user_id = a.doctor_id
        WHERE a.appointment_date = %s
    """
    params = [selected_date]
    if selected_doctor:
        query += " AND a.doctor_id = %s"
        params.append(selected_doctor)

    query += " ORDER BY a.appointment_time ASC"

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, tuple(params))
        appointments = cursor.fetchall() or []

    for appointment in appointments:
        appointment["appointment_time_display"] = _format_time(appointment.get("appointment_time"))

    return render_template(
        "appointments/appointment_dashboard.html",
        title="Appointments",
        active_page="appointments",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        appointments=appointments,
        selected_date=selected_date.isoformat(),
        doctors=_load_doctors(),
        selected_doctor=str(selected_doctor) if selected_doctor else "",
        status_options=STATUS_OPTIONS,
        csrf_token=generate_csrf_token(),
        doctor_view=False,
    )


@appointments_bp.get("/doctor")
@login_required
@role_required(DOCTOR_ROLES)
def doctor_schedule():
    selected_range = request.args.get("range", "today")
    today = _today_colombo()
    start_date = today
    end_date = today

    if selected_range == "week":
        end_date = today + timedelta(days=6)

    doctor_id = session.get("user_id")
    query = """
        SELECT a.appointment_id, a.patient_id, a.doctor_id, a.appointment_date,
               a.appointment_time, a.status, a.reason_for_visit,
         CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
         COALESCE(d.doctor_name, u.full_name, u.email) AS doctor_name
        FROM appointments a
        INNER JOIN patients p ON p.patient_id = a.patient_id
     LEFT JOIN doctors d ON d.doctor_id = a.doctor_id
     LEFT JOIN users u ON u.user_id = a.doctor_id
        WHERE a.doctor_id = %s
          AND a.appointment_date BETWEEN %s AND %s
        ORDER BY a.appointment_date ASC, a.appointment_time ASC
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (doctor_id, start_date, end_date))
        appointments = cursor.fetchall() or []

    for appointment in appointments:
        appointment["appointment_time_display"] = _format_time(appointment.get("appointment_time"))

    return render_template(
        "appointments/appointment_dashboard.html",
        title="My Schedule",
        active_page="appointments",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        appointments=appointments,
        selected_date=today.isoformat(),
        doctors=[],
        selected_doctor="",
        status_options=STATUS_OPTIONS,
        csrf_token=generate_csrf_token(),
        doctor_view=True,
        selected_range=selected_range,
    )


@appointments_bp.get("/book")
@login_required
@role_required(RECEPTION_ROLES)
def appointment_book_form():
    selected_date = _parse_date(request.args.get("date")) or _today_colombo()
    flash("Use Reception Desk for complete booking + billing + token flow.", "info")
    return redirect(url_for("appointments.reception_desk", date=selected_date.isoformat()))


@appointments_bp.post("/book")
@login_required
@role_required(RECEPTION_ROLES)
def appointment_book_submit():
    if not validate_csrf_token():
        flash("Invalid request token. Please retry.", "error")
        return redirect(url_for("appointments.appointment_book_form"))

    patient_id = request.form.get("patient_id")
    doctor_id = request.form.get("doctor_id")
    appointment_date = request.form.get("appointment_date")
    appointment_time = request.form.get("appointment_time")
    reason = (request.form.get("reason_for_visit") or "").strip()

    if not all([patient_id, doctor_id, appointment_date, appointment_time, reason]):
        flash("All booking fields are required.", "error")
        return redirect(url_for("appointments.appointment_book_form"))

    if not _parse_date(appointment_date):
        flash("Invalid appointment date.", "error")
        return redirect(url_for("appointments.appointment_book_form"))

    conflict_query = """
        SELECT 1
        FROM appointments
        WHERE doctor_id = %s
          AND appointment_date = %s
          AND appointment_time = %s
          AND status != 'Cancelled'
        LIMIT 1
    """

    insert_query = """
        INSERT INTO appointments (
            patient_id, doctor_id, appointment_date, appointment_time,
            status, reason_for_visit, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """

    patient_query = "SELECT phone_number FROM patients WHERE patient_id = %s"

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(conflict_query, (doctor_id, appointment_date, appointment_time))
        conflict = cursor.fetchone()
        if conflict:
            flash("This doctor is already booked for that time slot.", "error")
            return redirect(url_for("appointments.appointment_book_form"))

        cursor.execute(
            insert_query,
            (patient_id, doctor_id, appointment_date, appointment_time, "Scheduled", reason),
        )

        cursor.execute(patient_query, (patient_id,))
        patient = cursor.fetchone() or {}

    if patient.get("phone_number"):
        message = (
            f"MediCore: Your appointment is booked for {appointment_date} at {appointment_time}. "
            "Please arrive 10 minutes early."
        )
        send_sms(patient["phone_number"], message, patient_id=patient_id, message_type="Appointment Reminder")

    flash("Appointment booked successfully.", "success")
    return redirect(url_for("appointments.appointments_dashboard", date=appointment_date))


@appointments_bp.post("/update-status/<int:appointment_id>")
@login_required
@role_required(RECEPTION_ROLES)
def appointment_update_status(appointment_id: int):
    if not validate_csrf_token():
        flash("Invalid request token. Please retry.", "error")
        return redirect(url_for("appointments.appointments_dashboard"))

    new_status = request.form.get("status")
    if new_status not in STATUS_OPTIONS:
        flash("Invalid status selection.", "error")
        return redirect(url_for("appointments.appointments_dashboard"))

    update_query = """
        UPDATE appointments
        SET status = %s
        WHERE appointment_id = %s
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(update_query, (new_status, appointment_id))
        
        # --- Inventory Integration ---
        if new_status == "Completed":
            # 1. Find the invoice for this appointment
            cursor.execute("SELECT invoice_id FROM invoices WHERE appointment_id = %s", (appointment_id,))
            inv_row = cursor.fetchone()
            if inv_row:
                invoice_id = inv_row['invoice_id']
                # 2. Get all services (invoice_items) with service_item_id links
                cursor.execute("SELECT service_item_id, quantity FROM invoice_items WHERE invoice_id = %s AND service_item_id IS NOT NULL", (invoice_id,))
                items = cursor.fetchall() or []
                
                # 3. Reduce stock for each service item
                for item in items:
                    reduce_stock_for_service(
                        service_item_id=item['service_item_id'], 
                        service_qty=item['quantity'], 
                        ref_type='Bill', 
                        ref_id=str(appointment_id),
                        stage='on_completion',
                        user_id=session.get("user_id")
                    )

    flash("Appointment status updated.", "success")
    return redirect(url_for("appointments.appointments_dashboard"))


@appointments_bp.get("/reception-desk")
@login_required
@role_required(RECEPTION_ROLES)
def reception_desk():
    """Modern HIMS-style reception desk with dynamic services."""
    return render_template(
        "appointments/reception_desk_v2.html",
        title="Reception Desk - Service Booking",
        active_page="reception",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        csrf_token=generate_csrf_token(),
    )


@appointments_bp.get("/channeling-desk")
@login_required
@role_required(RECEPTION_ROLES)
def channeling_desk():
    """Redirect old channeling desk URL to modern reception desk."""
    return redirect(url_for("appointments.reception_desk"), 301)


@appointments_bp.get("/api/patient-lookup")
@login_required
@role_required(RECEPTION_ROLES)
def api_patient_lookup():
    phone = (request.args.get("phone") or "").strip()
    if not PHONE_PATTERN.match(phone):
        return jsonify({"ok": True, "patients": []})
    return jsonify({"ok": True, "patients": _patient_lookup_by_phone(phone)})


@appointments_bp.get("/api/doctor-meta")
@login_required
@role_required(RECEPTION_ROLES)
def api_doctor_meta():
    doctor_id_raw = (request.args.get("doctor_id") or "").strip()
    booking_date = _parse_date(request.args.get("date"))

    if not doctor_id_raw.isdigit() or not booking_date:
        return jsonify({"ok": False, "message": "Doctor and date are required."}), 400

    payload = _load_doctor_channeling_meta(int(doctor_id_raw), booking_date)
    payload["ok"] = True
    return jsonify(payload)
@appointments_bp.get("/api/services/categories")
@login_required
@role_required(RECEPTION_ROLES)
def api_get_service_categories():
    """API endpoint to fetch all active service categories for the reception desk."""
    query = """
        SELECT category_id, category_name, icon_class, display_order
        FROM service_categories
        WHERE is_active = TRUE
        ORDER BY display_order ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        categories = cursor.fetchall() or []
    return jsonify({"categories": categories})


@appointments_bp.get("/api/services/items/<int:category_id>")
@login_required
@role_required(RECEPTION_ROLES)
def api_get_service_items(category_id: int):
    """Fetch active service items for a category."""
    query = """
        SELECT si.item_id, si.item_code, si.item_name, si.price, si.description,
               si.linked_inventory_item_id,
               inv.quantity_on_hand AS inv_stock
        FROM service_items si
        LEFT JOIN inventory_items inv ON inv.item_id = si.linked_inventory_item_id
        WHERE si.category_id = %s AND si.is_active = TRUE
        ORDER BY si.display_order ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (category_id,))
        items = cursor.fetchall() or []

    # Serialise Decimal prices
    for item in items:
        item["price"] = float(item["price"]) if item.get("price") is not None else 0.0

    return jsonify({"items": items})




@appointments_bp.get("/api/services/all")
@login_required
@role_required(RECEPTION_ROLES)
def api_get_all_service_items():
    """API endpoint to fetch all active service items from all categories."""
    
    # 1. Fetch standard service items
    query_services = """
        SELECT si.item_id, si.item_code, si.item_name, si.price, si.description,
               sc.category_name, sc.category_id, 'service' as type
        FROM service_items si
        JOIN service_categories sc ON si.category_id = sc.category_id
        WHERE si.is_active = TRUE AND sc.is_active = TRUE
        ORDER BY sc.display_order ASC, si.display_order ASC
    """
    
    # 2. Fetch saleable inventory items (e.g. Pharmacy) to auto-expose them in Reception
    query_inventory = """
        SELECT i.item_id, i.item_code, i.item_name, i.selling_price as price, 
               CONCAT('Stock: ', i.quantity_on_hand, ' ', i.unit) as description,
               'Pharmacy' as category_name, 
               (SELECT category_id FROM service_categories WHERE category_name = 'Pharmacy' LIMIT 1) as category_id,
               'inventory' as type,
               i.quantity_on_hand as stock
        FROM inventory_items i
        WHERE i.is_saleable = TRUE AND i.status = 'Active' AND i.category = 'Pharmacy'
        ORDER BY i.item_name ASC
    """
    
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query_services)
        services = cursor.fetchall() or []
        
        cursor.execute(query_inventory)
        inventory = cursor.fetchall() or []
        
    items = services + inventory
    return jsonify({"items": items})


@appointments_bp.get("/api/inventory/saleable")
@login_required
@role_required(RECEPTION_ROLES)
def api_get_saleable_inventory():
    """API endpoint to fetch all active saleable inventory items for the reception desk."""
    query = """
        SELECT item_id, item_code, item_name, selling_price as price, quantity_on_hand as stock, category
        FROM inventory_items
        WHERE is_saleable = TRUE AND status = 'Active'
        ORDER BY item_name ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        items = cursor.fetchall() or []
    return jsonify({"items": items})
