from __future__ import annotations

from flask import Blueprint, jsonify, request

from medicore.communications.communications_service import send_sms
from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required


reception_bp = Blueprint("reception", __name__, url_prefix="/reception")

ALLOWED_ROLES = ["Receptionist", "Admin", "SuperAdmin"]


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