from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from medicore.communications.communications_service import send_sms, send_whatsapp_template
from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token

communications_bp = Blueprint("communications", __name__, url_prefix="/communications")

ALLOWED_ROLES = ["Admin", "SuperAdmin", "Receptionist"]


def _load_patients():
    query = """
        SELECT patient_id, first_name, last_name, phone_number
        FROM patients
        ORDER BY last_name, first_name
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _load_templates():
    query = """
        SELECT template_id, template_name, channel, content
        FROM communication_templates
        WHERE is_active = 1
        ORDER BY template_name
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


@communications_bp.get("")
@login_required
@role_required(ALLOWED_ROLES)
def communications_dashboard():
    logs_query = """
        SELECT l.log_id, l.patient_id, l.recipient_number, l.channel, l.message_type, l.content,
               l.status, l.timestamp, CONCAT(p.first_name, ' ', p.last_name) AS patient_name
        FROM communication_logs l
        LEFT JOIN patients p ON p.patient_id = l.patient_id
        ORDER BY l.timestamp DESC
        LIMIT 200
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(logs_query)
        logs = cursor.fetchall() or []

    return render_template(
        "communications/communications_dashboard.html",
        title="Communications",
        active_page="communications",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        logs=logs,
        patients=_load_patients(),
        templates=_load_templates(),
        csrf_token=generate_csrf_token(),
    )


@communications_bp.post("/send")
@login_required
@role_required(ALLOWED_ROLES)
def send_manual_message():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("communications.communications_dashboard"))

    patient_id = request.form.get("patient_id")
    channel = request.form.get("channel")
    template_name = request.form.get("template_name")
    custom_message = (request.form.get("custom_message") or "").strip()

    patient_query = "SELECT phone_number FROM patients WHERE patient_id = %s"
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(patient_query, (patient_id,))
        patient = cursor.fetchone()

    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("communications.communications_dashboard"))

    number = patient.get("phone_number")

    if channel == "SMS":
        send_sms(number, custom_message, patient_id=patient_id, message_type="Manual")
    elif channel == "WhatsApp":
        variables = [custom_message] if custom_message else ["Notification"]
        send_whatsapp_template(number, template_name or "general_alert", variables, patient_id, "Manual")
    else:
        flash("Unsupported channel.", "error")
        return redirect(url_for("communications.communications_dashboard"))

    flash("Message queued for delivery.", "success")
    return redirect(url_for("communications.communications_dashboard"))
