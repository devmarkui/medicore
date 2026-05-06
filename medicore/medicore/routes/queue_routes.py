from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for, flash

from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token

queue_bp = Blueprint("queue", __name__, url_prefix="/queue")

ALLOWED_ROLES = ["Receptionist", "Doctor", "Admin", "SuperAdmin"]


def _today_colombo():
    return datetime.now(ZoneInfo("Asia/Colombo")).date()


@queue_bp.post("/check-in/<int:appointment_id>")
@login_required
@role_required(ALLOWED_ROLES)
def check_in(appointment_id: int):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("appointments.appointments_dashboard"))

    appointment_query = """
        SELECT appointment_id, patient_id, doctor_id, appointment_date
        FROM appointments
        WHERE appointment_id = %s
        LIMIT 1
    """
    next_queue_query = """
    SELECT COALESCE(MAX(queue_number), 0) AS max_queue
    FROM physical_queues
    WHERE doctor_id = %s AND queue_date = %s
    """
    insert_queue = """
    INSERT INTO physical_queues (patient_id, doctor_id, queue_date, queue_number, status)
        VALUES (%s, %s, %s, %s, 'Waiting')
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(appointment_query, (appointment_id,))
        appointment = cursor.fetchone()
        if not appointment:
            flash("Appointment not found.", "error")
            return redirect(url_for("appointments.appointments_dashboard"))

        cursor.execute(next_queue_query, (appointment["doctor_id"], appointment["appointment_date"]))
        max_queue = cursor.fetchone() or {}
        queue_number = int(max_queue.get("max_queue", 0)) + 1

        cursor.execute(
            insert_queue,
            (appointment["patient_id"], appointment["doctor_id"], appointment["appointment_date"], queue_number),
        )

    flash(f"Patient checked in with queue number {queue_number}.", "success")
    return redirect(url_for("queue.queue_manager"))


@queue_bp.get("/manager")
@login_required
@role_required(ALLOWED_ROLES)
def queue_manager():
    today = _today_colombo()
    query = """
        SELECT q.queue_id, q.queue_number, q.status,
               CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
               COALESCE(u.full_name, u.email) AS doctor_name
        FROM physical_queues q
        INNER JOIN patients p ON p.patient_id = q.patient_id
        INNER JOIN users u ON u.user_id = q.doctor_id
    WHERE q.queue_date = %s
        ORDER BY q.queue_number ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (today,))
        queues = cursor.fetchall() or []

    return render_template(
        "queue/reception_queue_manager.html",
        title="Queue Manager",
        active_page="queue",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        queues=queues,
        csrf_token=generate_csrf_token(),
    )


@queue_bp.post("/update/<int:queue_id>")
@login_required
@role_required(ALLOWED_ROLES)
def update_queue(queue_id: int):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("queue.queue_manager"))

    new_status = request.form.get("status")
    if new_status not in ["Waiting", "In Consultation", "Completed"]:
        flash("Invalid status.", "error")
        return redirect(url_for("queue.queue_manager"))

    query = "UPDATE physical_queues SET status = %s WHERE queue_id = %s"
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (new_status, queue_id))

    flash("Queue status updated.", "success")
    return redirect(url_for("queue.queue_manager"))


@queue_bp.get("/display")
@login_required
@role_required(ALLOWED_ROLES)
def queue_display_data():
    today = _today_colombo()
    query = """
        SELECT q.queue_number, q.status,
               COALESCE(u.full_name, u.email) AS doctor_name
        FROM physical_queues q
        INNER JOIN users u ON u.user_id = q.doctor_id
    WHERE q.queue_date = %s AND q.status IN ('Waiting', 'In Consultation')
        ORDER BY q.queue_number ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (today,))
        queues = cursor.fetchall() or []

    return jsonify(queues)
