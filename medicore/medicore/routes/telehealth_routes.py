from __future__ import annotations

import uuid

from flask import Blueprint, flash, redirect, session, url_for

from medicore.communications.communications_service import send_whatsapp_template
from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import validate_csrf_token

telehealth_bp = Blueprint("telehealth", __name__, url_prefix="/telehealth")

ALLOWED_ROLES = ["Doctor", "Receptionist", "Admin", "SuperAdmin"]


def _generate_meeting_link() -> str:
    return f"https://meet.jit.si/MediCore-{uuid.uuid4().hex}"


@telehealth_bp.post("/generate-link/<int:appointment_id>")
@login_required
@role_required(ALLOWED_ROLES)
def generate_link(appointment_id: int):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("appointments.appointments_dashboard"))

    appointment_query = """
        SELECT a.appointment_id, a.patient_id, p.phone_number
        FROM appointments a
        INNER JOIN patients p ON p.patient_id = a.patient_id
        WHERE a.appointment_id = %s
        LIMIT 1
    """
    update_query = """
        UPDATE appointments
        SET telehealth_link = %s, appointment_mode = 'Online'
        WHERE appointment_id = %s
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(appointment_query, (appointment_id,))
        appointment = cursor.fetchone()
        if not appointment:
            flash("Appointment not found.", "error")
            return redirect(url_for("appointments.appointments_dashboard"))
        link = _generate_meeting_link()
        cursor.execute(update_query, (link, appointment_id))

    if appointment.get("phone_number"):
        send_whatsapp_template(
            appointment["phone_number"],
            template_name="telehealth_link",
            variables=[link],
            patient_id=appointment.get("patient_id"),
            message_type="Appointment Reminder",
        )

    flash("Telehealth link generated and sent.", "success")
    return redirect(url_for("appointments.appointments_dashboard"))
