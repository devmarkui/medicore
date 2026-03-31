from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token
from medicore.communications.communications_service import send_sms

appointments_bp = Blueprint("appointments", __name__, url_prefix="/appointments")

STATUS_OPTIONS = ["Scheduled", "Checked-In", "Completed", "Cancelled"]
RECEPTION_ROLES = ["Receptionist", "Admin", "SuperAdmin"]
DOCTOR_ROLES = ["Doctor", "SuperAdmin"]


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
        SELECT u.id, COALESCE(u.full_name, u.username) AS doctor_name
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        WHERE r.role_name = %s AND u.is_active = 1
        ORDER BY doctor_name
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, ("Doctor",))
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
               COALESCE(u.full_name, u.username) AS doctor_name
        FROM appointments a
        INNER JOIN patients p ON p.patient_id = a.patient_id
        INNER JOIN users u ON u.id = a.doctor_id
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
               COALESCE(u.full_name, u.username) AS doctor_name
        FROM appointments a
        INNER JOIN patients p ON p.patient_id = a.patient_id
        INNER JOIN users u ON u.id = a.doctor_id
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
    return render_template(
        "appointments/appointment_book.html",
        title="Book Appointment",
        active_page="appointments",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        patients=_load_patients(),
        doctors=_load_doctors(),
        time_slots=_build_time_slots(),
        selected_date=selected_date.isoformat(),
        csrf_token=generate_csrf_token(),
    )


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

    flash("Appointment status updated.", "success")
    return redirect(url_for("appointments.appointments_dashboard"))
