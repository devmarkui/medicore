from __future__ import annotations

import os
from datetime import datetime, date, timedelta, time
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for, send_file

from medicore.db.connection import get_db_cursor
from medicore.security.passwords import verify_password
from medicore.security.web import generate_csrf_token, validate_csrf_token

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")

PAGE_SIZE = 25
DEPARTMENT_OPTIONS = [
    "General Medicine",
    "Pediatrics",
    "Cardiology",
    "Orthopedics",
    "Dermatology",
    "ENT",
    "Gynecology",
]


def patient_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("portal_patient_id"):
            flash("Please sign in to continue.", "error")
            return redirect(url_for("portal.portal_login"))
        return view_func(*args, **kwargs)

    return wrapper


def _portal_user_context() -> dict:
    return {
        "patient_id": session.get("portal_patient_id"),
        "name": session.get("portal_patient_name"),
        "email": session.get("portal_patient_email"),
    }


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


def _load_departments() -> list[dict]:
    query = """
        SELECT department_id, department_name
        FROM departments
        WHERE status = 'Active'
        ORDER BY department_name
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _load_doctors(department_id: str | None = None) -> list[dict]:
    query = """
        SELECT u.id, COALESCE(u.full_name, u.username) AS doctor_name, u.department_id
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        WHERE r.role_name = %s AND u.is_active = 1
    """
    params = ["Doctor"]
    if department_id:
        query += " AND u.department_id = %s"
        params.append(department_id)
    query += " ORDER BY doctor_name"

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, tuple(params))
        return cursor.fetchall() or []


def _load_patient_login(nic_identifier: str, email_identifier: str) -> dict | None:
    query = """
        SELECT patient_id, first_name, last_name, email, nic_number, password_hash, portal_active
        FROM patients
        WHERE nic_number = %s OR email = %s
        LIMIT 1
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (nic_identifier, email_identifier))
        return cursor.fetchone()


@portal_bp.get("/login")
def portal_login():
    if session.get("portal_patient_id"):
        return redirect(url_for("portal.portal_dashboard"))

    return render_template(
        "portal/portal_login.html",
        title="Patient Portal Login",
        csrf_token=generate_csrf_token(),
    )


@portal_bp.post("/login")
def portal_login_submit():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("portal.portal_login"))

    identifier = (request.form.get("identifier") or "").strip()
    password = (request.form.get("password") or "").strip()

    if not identifier or not password:
        flash("Please enter your NIC/email and password.", "error")
        return redirect(url_for("portal.portal_login"))

    patient = _load_patient_login(identifier.upper(), identifier.lower())
    if not patient or not patient.get("password_hash"):
        flash("Invalid credentials.", "error")
        return redirect(url_for("portal.portal_login"))

    if not patient.get("portal_active"):
        flash("Patient portal access is not enabled. Please contact the clinic.", "error")
        return redirect(url_for("portal.portal_login"))

    if not verify_password(patient["password_hash"], password):
        flash("Invalid credentials.", "error")
        return redirect(url_for("portal.portal_login"))

    session["portal_patient_id"] = patient["patient_id"]
    session["portal_patient_name"] = f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip()
    session["portal_patient_email"] = patient.get("email")

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            "UPDATE patients SET portal_last_login = NOW() WHERE patient_id = %s",
            (patient["patient_id"],),
        )

    flash("Welcome back!", "success")
    return redirect(url_for("portal.portal_dashboard"))


@portal_bp.get("/logout")
@patient_required
def portal_logout():
    session.pop("portal_patient_id", None)
    session.pop("portal_patient_name", None)
    session.pop("portal_patient_email", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("portal.portal_login"))


@portal_bp.get("")
@patient_required
def portal_dashboard():
    patient_id = session.get("portal_patient_id")
    upcoming_query = """
        SELECT a.appointment_id, a.appointment_date, a.appointment_time, a.status,
               a.reason_for_visit, COALESCE(u.full_name, u.username) AS doctor_name
        FROM appointments a
        INNER JOIN users u ON u.id = a.doctor_id
        WHERE a.patient_id = %s
          AND a.status IN ('Scheduled', 'Checked-In')
          AND a.appointment_date >= CURDATE()
        ORDER BY a.appointment_date ASC, a.appointment_time ASC
        LIMIT 1
    """

    history_query = """
        SELECT a.appointment_id, a.appointment_date, a.appointment_time, a.status,
               COALESCE(u.full_name, u.username) AS doctor_name
        FROM appointments a
        INNER JOIN users u ON u.id = a.doctor_id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
        LIMIT 5
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(upcoming_query, (patient_id,))
        upcoming = cursor.fetchone()
        cursor.execute(history_query, (patient_id,))
        recent_visits = cursor.fetchall() or []

    if upcoming:
        upcoming["appointment_time_display"] = _format_time(upcoming.get("appointment_time"))
    for visit in recent_visits:
        visit["appointment_time_display"] = _format_time(visit.get("appointment_time"))

    return render_template(
        "portal/portal_dashboard.html",
        title="Patient Portal",
        portal_user=_portal_user_context(),
        upcoming=upcoming,
        recent_visits=recent_visits,
        csrf_token=generate_csrf_token(),
    )


@portal_bp.post("/appointments/<int:appointment_id>/cancel")
@patient_required
def portal_cancel_appointment(appointment_id: int):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("portal.portal_dashboard"))

    patient_id = session.get("portal_patient_id")
    update_query = """
        UPDATE appointments
        SET status = 'Cancelled'
        WHERE appointment_id = %s AND patient_id = %s AND status != 'Cancelled'
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(update_query, (appointment_id, patient_id))

    flash("Appointment cancelled.", "success")
    return redirect(url_for("portal.portal_dashboard"))


@portal_bp.get("/records")
@patient_required
def portal_records():
    patient_id = session.get("portal_patient_id")

    prescriptions_query = """
        SELECT p.prescription_id, p.prescription_date, p.general_instructions,
               COALESCE(u.full_name, u.username) AS doctor_name
        FROM prescriptions p
        LEFT JOIN users u ON u.id = p.doctor_id
        WHERE p.patient_id = %s
        ORDER BY p.prescription_date DESC
        LIMIT 20
    """

    lab_query = """
        SELECT r.result_id, o.order_id, o.order_date, t.test_name, r.result_value,
               r.is_abnormal, r.report_file_path
        FROM lab_results r
        INNER JOIN lab_orders o ON o.order_id = r.order_id
        INNER JOIN lab_tests_master t ON t.test_id = r.test_id
        WHERE o.patient_id = %s AND o.status = 'Completed'
        ORDER BY o.order_date DESC, r.result_id DESC
        LIMIT 50
    """

    invoices_query = """
        SELECT invoice_id, created_at, total_amount, status
        FROM invoices
        WHERE patient_id = %s
        ORDER BY created_at DESC
        LIMIT 20
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(prescriptions_query, (patient_id,))
        prescriptions = cursor.fetchall() or []
        cursor.execute(lab_query, (patient_id,))
        lab_results = cursor.fetchall() or []
        cursor.execute(invoices_query, (patient_id,))
        invoices = cursor.fetchall() or []

    return render_template(
        "portal/portal_records.html",
        title="My Records",
        portal_user=_portal_user_context(),
        prescriptions=prescriptions,
        lab_results=lab_results,
        invoices=invoices,
        csrf_token=generate_csrf_token(),
    )


@portal_bp.get("/lab-report/<int:result_id>/download")
@patient_required
def portal_download_lab_report(result_id: int):
    patient_id = session.get("portal_patient_id")
    query = """
        SELECT r.report_file_path
        FROM lab_results r
        INNER JOIN lab_orders o ON o.order_id = r.order_id
        WHERE r.result_id = %s
          AND o.patient_id = %s
          AND o.status = 'Completed'
          AND r.report_file_path IS NOT NULL
        LIMIT 1
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (result_id, patient_id))
        result = cursor.fetchone()

    file_path = (result or {}).get("report_file_path")
    if not file_path or not os.path.exists(file_path):
        flash("Report file not found.", "error")
        return redirect(url_for("portal.portal_records"))

    return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))


@portal_bp.get("/book")
@patient_required
def portal_book():
    selected_department = request.args.get("department") or ""
    selected_doctor = request.args.get("doctor_id") or ""
    selected_date = _parse_date(request.args.get("date"))
    reschedule_id = request.args.get("appointment_id")

    reschedule_appointment = None
    if reschedule_id:
        query = """
            SELECT appointment_id, doctor_id, appointment_date, appointment_time, reason_for_visit
            FROM appointments
            WHERE appointment_id = %s AND patient_id = %s AND status != 'Cancelled'
        """
        with get_db_cursor(dictionary=True) as (_conn, cursor):
            cursor.execute(query, (reschedule_id, session.get("portal_patient_id")))
            reschedule_appointment = cursor.fetchone()
        if reschedule_appointment:
            selected_doctor = str(reschedule_appointment.get("doctor_id"))
            selected_date = reschedule_appointment.get("appointment_date")
            reschedule_appointment["appointment_time_display"] = _format_time(
                reschedule_appointment.get("appointment_time")
            )

    available_slots: list[str] = []
    if selected_doctor and selected_date:
        conflict_query = """
            SELECT appointment_time
            FROM appointments
            WHERE doctor_id = %s
              AND appointment_date = %s
              AND status != 'Cancelled'
        """
        with get_db_cursor(dictionary=True) as (_conn, cursor):
            cursor.execute(conflict_query, (selected_doctor, selected_date))
            booked = { _format_time(row.get("appointment_time")) for row in (cursor.fetchall() or []) }
        available_slots = [slot for slot in _build_time_slots() if slot not in booked]

    departments = _load_departments()
    if not departments:
        departments = [{"department_id": None, "department_name": name} for name in DEPARTMENT_OPTIONS]

    return render_template(
        "portal/portal_book.html",
        title="Book Appointment",
        portal_user=_portal_user_context(),
        departments=departments,
        doctors=_load_doctors(selected_department or None),
        selected_department=str(selected_department) if selected_department else "",
        selected_doctor=str(selected_doctor) if selected_doctor else "",
        selected_date=selected_date.isoformat() if selected_date else "",
        available_slots=available_slots,
        reschedule=reschedule_appointment,
        csrf_token=generate_csrf_token(),
    )


@portal_bp.post("/book")
@patient_required
def portal_book_submit():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("portal.portal_book"))

    patient_id = session.get("portal_patient_id")
    doctor_id = request.form.get("doctor_id")
    appointment_date = request.form.get("appointment_date")
    appointment_time = request.form.get("appointment_time")
    reason = (request.form.get("reason_for_visit") or "").strip()
    appointment_id = request.form.get("appointment_id")

    if not all([doctor_id, appointment_date, appointment_time, reason]):
        flash("Please complete all booking fields.", "error")
        return redirect(url_for("portal.portal_book"))

    if not _parse_date(appointment_date):
        flash("Invalid appointment date.", "error")
        return redirect(url_for("portal.portal_book"))

    if appointment_id:
        conflict_query = """
            SELECT 1
            FROM appointments
            WHERE doctor_id = %s
              AND appointment_date = %s
              AND appointment_time = %s
              AND status != 'Cancelled'
              AND appointment_id != %s
            LIMIT 1
        """
        update_query = """
            UPDATE appointments
            SET doctor_id = %s, appointment_date = %s, appointment_time = %s, reason_for_visit = %s, status = 'Scheduled'
            WHERE appointment_id = %s AND patient_id = %s
        """
        with get_db_cursor(dictionary=True) as (_conn, cursor):
            cursor.execute(conflict_query, (doctor_id, appointment_date, appointment_time, appointment_id))
            if cursor.fetchone():
                flash("That time slot is already booked.", "error")
                return redirect(url_for("portal.portal_book", appointment_id=appointment_id))
            cursor.execute(update_query, (doctor_id, appointment_date, appointment_time, reason, appointment_id, patient_id))
        flash("Appointment rescheduled.", "success")
    else:
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
        with get_db_cursor(dictionary=True) as (_conn, cursor):
            cursor.execute(conflict_query, (doctor_id, appointment_date, appointment_time))
            if cursor.fetchone():
                flash("That time slot is already booked.", "error")
                return redirect(url_for("portal.portal_book"))
            cursor.execute(insert_query, (patient_id, doctor_id, appointment_date, appointment_time, "Scheduled", reason))
        flash("Appointment booked successfully.", "success")

    return redirect(url_for("portal.portal_dashboard"))


@portal_bp.get("/message")
@patient_required
def portal_message():
    return render_template(
        "portal/portal_message.html",
        title="Message Clinic",
        portal_user=_portal_user_context(),
        csrf_token=generate_csrf_token(),
    )


@portal_bp.post("/message")
@patient_required
def portal_message_submit():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("portal.portal_message"))

    subject = (request.form.get("subject") or "").strip()
    message = (request.form.get("message") or "").strip()
    if not subject or not message:
        flash("Please provide both a subject and message.", "error")
        return redirect(url_for("portal.portal_message"))

    patient_id = session.get("portal_patient_id")
    log_query = """
        INSERT INTO communication_logs (
            patient_id, recipient_number, channel, direction, message_type, content, status
        ) VALUES (%s, %s, 'Email', 'Inbound', 'Manual', %s, 'Queued')
    """
    recipient_number = session.get("portal_patient_email") or "Portal"
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(log_query, (patient_id, recipient_number, f"{subject}: {message}"))

    flash("Your message has been sent to the clinic.", "success")
    return redirect(url_for("portal.portal_dashboard"))
