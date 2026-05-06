from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token
from medicore.utils.timezone import get_colombo_time

clinical_refinements_bp = Blueprint("clinical_refinements", __name__, url_prefix="/clinical")

DOCTOR_ROLES = ["Doctor", "SuperAdmin"]


def _load_patient_snapshot(patient_id: str) -> dict | None:
    query = """
        SELECT p.patient_id, p.nic_number, p.first_name, p.last_name, p.date_of_birth,
               p.gender, p.phone_number, p.email, p.blood_group,
               mh.allergies, mh.chronic_conditions, mh.past_surgeries, mh.family_history
        FROM patients p
        LEFT JOIN medical_history mh ON mh.patient_id = p.patient_id
        WHERE p.patient_id = %s
        LIMIT 1
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (patient_id,))
        return cursor.fetchone()


def _load_latest_vitals(patient_id: str) -> dict | None:
    query = """
        SELECT v.blood_pressure, v.heart_rate, v.temperature, v.weight_kg, v.height_cm,
               v.record_date, COALESCE(u.full_name, u.email) AS recorded_by
        FROM patient_vitals v
        LEFT JOIN users u ON u.user_id = v.recorded_by
        WHERE v.patient_id = %s
        ORDER BY v.record_date DESC
        LIMIT 1
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (patient_id,))
        return cursor.fetchone()


@clinical_refinements_bp.get("/referral/<patient_id>")
@login_required
@role_required(DOCTOR_ROLES)
def referral_builder(patient_id: str):
    patient = _load_patient_snapshot(patient_id)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("appointments.appointments_dashboard"))

    latest_vitals = _load_latest_vitals(patient_id)

    return render_template(
        "clinical/referral_builder.html",
        title="Referral Letter",
        active_page="clinical",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        patient=patient,
        latest_vitals=latest_vitals,
        csrf_token=generate_csrf_token(),
    )


@clinical_refinements_bp.post("/referral/create")
@login_required
@role_required(DOCTOR_ROLES)
def referral_create():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("appointments.appointments_dashboard"))

    patient_id = request.form.get("patient_id")
    referred_to_specialty = (request.form.get("referred_to_specialty") or "").strip()
    clinical_justification = (request.form.get("clinical_justification") or "").strip()

    if not all([patient_id, referred_to_specialty, clinical_justification]):
        flash("All referral fields are required.", "error")
        return redirect(url_for("clinical_refinements.referral_builder", patient_id=patient_id))

    insert_query = """
        INSERT INTO referral_letters (
            patient_id, referring_doctor_id, referred_to_specialty, clinical_justification, created_at
        ) VALUES (%s, %s, %s, %s, %s)
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            insert_query,
            (patient_id, session.get("user_id"), referred_to_specialty, clinical_justification, get_colombo_time()),
        )

    flash("Referral letter saved.", "success")
    return redirect(url_for("clinical_refinements.patient_summary", patient_id=patient_id))


@clinical_refinements_bp.get("/summary/<patient_id>")
@login_required
@role_required(DOCTOR_ROLES)
def patient_summary(patient_id: str):
    patient = _load_patient_snapshot(patient_id)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("appointments.appointments_dashboard"))

    vitals_query = """
        SELECT v.blood_pressure, v.heart_rate, v.temperature, v.weight_kg, v.height_cm,
               v.record_date, COALESCE(u.full_name, u.email) AS recorded_by
        FROM patient_vitals v
        LEFT JOIN users u ON u.user_id = v.recorded_by
        WHERE v.patient_id = %s
        ORDER BY v.record_date DESC
        LIMIT 20
    """
    consultations_query = """
        SELECT c.consultation_id, c.consultation_date, c.chief_complaint,
               c.diagnosis, c.clinical_notes,
               COALESCE(u.full_name, u.email) AS doctor_name
        FROM consultations c
        LEFT JOIN users u ON u.user_id = c.doctor_id
        WHERE c.patient_id = %s
        ORDER BY c.consultation_date DESC
        LIMIT 50
    """
    prescriptions_query = """
        SELECT p.prescription_id, p.prescription_date, p.general_instructions,
               COALESCE(u.full_name, u.email) AS doctor_name
        FROM prescriptions p
        LEFT JOIN users u ON u.user_id = p.doctor_id
        WHERE p.patient_id = %s
        ORDER BY p.prescription_date DESC
        LIMIT 50
    """
    prescription_items_query = """
        SELECT i.prescription_id, i.dosage, i.frequency, i.duration_days, i.special_instructions,
               d.generic_name, d.brand_name, d.strength
        FROM prescription_items i
        INNER JOIN drugs_master d ON d.drug_id = i.drug_id
        WHERE i.prescription_id IN ({placeholders})
        ORDER BY i.item_id ASC
    """
    lab_query = """
        SELECT o.order_id, o.order_date, o.status,
               t.test_name, r.result_value, r.is_abnormal
        FROM lab_orders o
        INNER JOIN lab_results r ON r.order_id = o.order_id
        INNER JOIN lab_tests_master t ON t.test_id = r.test_id
        WHERE o.patient_id = %s
        ORDER BY o.order_date DESC, r.result_id DESC
        LIMIT 100
    """
    insurance_query = """
        SELECT provider_name, policy_number, expiry_date
        FROM patient_insurance
        WHERE patient_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(vitals_query, (patient_id,))
        vitals = cursor.fetchall() or []
        cursor.execute(consultations_query, (patient_id,))
        consultations = cursor.fetchall() or []
        cursor.execute(prescriptions_query, (patient_id,))
        prescriptions = cursor.fetchall() or []
        cursor.execute(lab_query, (patient_id,))
        lab_results = cursor.fetchall() or []
        cursor.execute(insurance_query, (patient_id,))
        insurance = cursor.fetchone()

        items_by_prescription: dict[str, list[dict]] = defaultdict(list)
        if prescriptions:
            placeholders = ",".join(["%s"] * len(prescriptions))
            query = prescription_items_query.format(placeholders=placeholders)
            cursor.execute(query, tuple([p["prescription_id"] for p in prescriptions]))
            for item in cursor.fetchall() or []:
                items_by_prescription[item["prescription_id"]].append(item)

    summary_payload = {
        "patient": patient,
        "insurance": insurance,
        "vitals": vitals,
        "consultations": consultations,
        "prescriptions": prescriptions,
        "prescription_items": items_by_prescription,
        "lab_results": lab_results,
        "generated_at": get_colombo_time(),
    }

    return render_template(
        "clinical/patient_summary_report.html",
        title="Patient Summary",
        active_page="clinical",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        summary=summary_payload,
        csrf_token=generate_csrf_token(),
    )
