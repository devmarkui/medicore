from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for, flash

from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token

clinical_bp = Blueprint("clinical", __name__, url_prefix="/clinical")

ALLOWED_ROLES = ["Doctor"]


def _today_colombo() -> datetime:
    return datetime.now(ZoneInfo("Asia/Colombo"))


def _calculate_age(dob: date | None) -> int | None:
    if not dob:
        return None
    today = _today_colombo().date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _generate_prescription_id(cursor) -> str:
    year_suffix = _today_colombo().strftime("%y")
    prefix = f"RX-{year_suffix}-"
    cursor.execute("SELECT COUNT(*) AS total FROM prescriptions WHERE prescription_id LIKE %s", (f"{prefix}%",))
    total = (cursor.fetchone() or {}).get("total", 0)
    sequence = int(total) + 1
    return f"{prefix}{sequence:04d}"


def _validate_csrf_from_json(payload: dict) -> bool:
    token = (payload or {}).get("csrf_token")
    return bool(token) and token == session.get("csrf_token")


@clinical_bp.get("/workspace/<int:appointment_id>")
@login_required
@role_required(ALLOWED_ROLES)
def clinical_workspace(appointment_id: int):
    appointment_query = """
        SELECT a.appointment_id, a.patient_id, a.doctor_id, a.appointment_date,
               a.appointment_time, a.status,
               CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
               p.date_of_birth, p.blood_group, p.phone_number,
               p.emergency_contact_name, p.emergency_contact_phone,
               mh.allergies, mh.chronic_conditions, mh.past_surgeries, mh.family_history
        FROM appointments a
        INNER JOIN patients p ON p.patient_id = a.patient_id
        LEFT JOIN medical_history mh ON mh.patient_id = p.patient_id
        WHERE a.appointment_id = %s
        LIMIT 1
    """

    vitals_query = """
        SELECT v.blood_pressure, v.heart_rate, v.temperature, v.weight_kg, v.height_cm,
               v.record_date, COALESCE(u.full_name, u.email) AS recorded_by
        FROM patient_vitals v
        LEFT JOIN users u ON u.user_id = v.recorded_by
        WHERE v.patient_id = %s
        ORDER BY v.record_date DESC
        LIMIT 1
    """

    consultations_query = """
        SELECT c.consultation_id, c.consultation_date, c.chief_complaint, c.diagnosis,
               COALESCE(u.full_name, u.email) AS doctor_name
        FROM consultations c
        LEFT JOIN users u ON u.user_id = c.doctor_id
        WHERE c.patient_id = %s
        ORDER BY c.consultation_date DESC
        LIMIT 15
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(appointment_query, (appointment_id,))
        appointment = cursor.fetchone()
        if not appointment:
            flash("Appointment not found.", "error")
            return redirect(url_for("appointments.appointments_dashboard"))
        cursor.execute(vitals_query, (appointment["patient_id"],))
        latest_vitals = cursor.fetchone()
        cursor.execute(consultations_query, (appointment["patient_id"],))
        consultations = cursor.fetchall() or []

    patient_age = _calculate_age(appointment.get("date_of_birth"))

    return render_template(
        "clinical/clinical_workspace.html",
        title="Clinical Workspace",
        active_page="clinical",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        appointment=appointment,
        latest_vitals=latest_vitals,
        consultations=consultations,
        patient_age=patient_age,
        csrf_token=generate_csrf_token(),
    )


@clinical_bp.get("/api/drugs/search")
@login_required
@role_required(ALLOWED_ROLES)
def drugs_search():
    query_text = (request.args.get("q") or "").strip()
    if not query_text:
        return jsonify([])

    like_term = f"%{query_text}%"
    query = """
        SELECT drug_id, generic_name, brand_name, form, strength
        FROM drugs_master
        WHERE generic_name LIKE %s OR brand_name LIKE %s
        ORDER BY generic_name ASC
        LIMIT 20
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (like_term, like_term))
        drugs = cursor.fetchall() or []

    return jsonify(drugs)


@clinical_bp.post("/prescription/save")
@login_required
@role_required(ALLOWED_ROLES)
def prescription_save():
    payload = request.get_json(silent=True) or {}
    if not _validate_csrf_from_json(payload):
        return jsonify({"error": "Invalid CSRF token"}), 400

    appointment_id = payload.get("appointment_id")
    patient_id = payload.get("patient_id")
    diagnosis = (payload.get("diagnosis") or "").strip()
    chief_complaint = (payload.get("chief_complaint") or "").strip()
    clinical_notes = (payload.get("clinical_notes") or "").strip()
    general_instructions = (payload.get("general_instructions") or "").strip()
    items = payload.get("items") or []

    if not appointment_id or not patient_id or not items:
        return jsonify({"error": "Missing required fields"}), 400

    consultation_insert = """
        INSERT INTO consultations (patient_id, doctor_id, consultation_date, chief_complaint, clinical_notes, diagnosis)
        VALUES (%s, %s, NOW(), %s, %s, %s)
    """
    prescription_insert = """
        INSERT INTO prescriptions (prescription_id, consultation_id, patient_id, doctor_id, prescription_date, general_instructions)
        VALUES (%s, %s, %s, %s, NOW(), %s)
    """
    items_insert = """
        INSERT INTO prescription_items (prescription_id, drug_id, dosage, frequency, duration_days, special_instructions)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    doctor_id = session.get("user_id")

    with get_db_cursor(dictionary=True) as (conn, cursor):
        conn.start_transaction()
        cursor.execute(consultation_insert, (patient_id, doctor_id, chief_complaint, clinical_notes, diagnosis))
        consultation_id = cursor.lastrowid
        prescription_id = _generate_prescription_id(cursor)
        cursor.execute(
            prescription_insert,
            (prescription_id, consultation_id, patient_id, doctor_id, general_instructions),
        )
        for item in items:
            cursor.execute(
                items_insert,
                (
                    prescription_id,
                    item.get("drug_id"),
                    item.get("dosage"),
                    item.get("frequency"),
                    item.get("duration_days"),
                    item.get("special_instructions"),
                ),
            )

    return jsonify({
        "prescription_id": prescription_id,
        "redirect_url": url_for("clinical.prescription_print", prescription_id=prescription_id)
    })


@clinical_bp.get("/prescription/<prescription_id>/print")
@login_required
@role_required(ALLOWED_ROLES)
def prescription_print(prescription_id: str):
    prescription_query = """
        SELECT p.prescription_id, p.prescription_date, p.general_instructions,
               CONCAT(pt.first_name, ' ', pt.last_name) AS patient_name,
               pt.date_of_birth, pt.blood_group,
               COALESCE(u.full_name, u.email) AS doctor_name
        FROM prescriptions p
        INNER JOIN patients pt ON pt.patient_id = p.patient_id
        INNER JOIN users u ON u.user_id = p.doctor_id
        WHERE p.prescription_id = %s
        LIMIT 1
    """
    items_query = """
        SELECT i.dosage, i.frequency, i.duration_days, i.special_instructions,
               d.generic_name, d.brand_name, d.form, d.strength
        FROM prescription_items i
        INNER JOIN drugs_master d ON d.drug_id = i.drug_id
        WHERE i.prescription_id = %s
        ORDER BY i.item_id ASC
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(prescription_query, (prescription_id,))
        prescription = cursor.fetchone()
        if not prescription:
            flash("Prescription not found.", "error")
            return redirect(url_for("appointments.appointments_dashboard"))
        cursor.execute(items_query, (prescription_id,))
        items = cursor.fetchall() or []

    patient_age = _calculate_age(prescription.get("date_of_birth"))

    return render_template(
        "clinical/prescription_print.html",
        title=f"Prescription {prescription_id}",
        active_page="clinical",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        prescription=prescription,
        items=items,
        patient_age=patient_age,
    )
