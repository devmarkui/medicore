from __future__ import annotations

import re
from datetime import datetime, date
from math import ceil

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token

patients_bp = Blueprint("patients", __name__, url_prefix="/patients")
patient_profile_bp = Blueprint("patient_profile", __name__, url_prefix="/patient")

ALLOWED_ROLES = ["Receptionist", "Admin", "SuperAdmin", "Doctor"]
PROFILE_VIEW_ROLES = ["Receptionist", "Nurse", "Doctor", "Admin", "SuperAdmin"]
PROFILE_EDIT_ROLES = ["Nurse", "Doctor", "Admin", "SuperAdmin"]
PAGE_SIZE = 15
PATIENT_ID_BASE = 1000
PATIENT_NUMBER_BASE = 1000
PHONE_PATTERN = re.compile(r"^\d{10}$")
NAME_PATTERN = re.compile(r"^[A-Za-z ]{2,}$")
NIC_PATTERN = re.compile(r"^(\d{9}[VvXx]|\d{12})$")


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _calculate_age(dob: date | None) -> int | None:
    if not dob:
        return None
    today = datetime.utcnow().date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _estimate_dob_from_age(age: int) -> date:
    today = datetime.utcnow().date()
    year = today.year - age
    try:
        return date(year, today.month, today.day)
    except ValueError:
        # Handles leap-day edge case for non-leap years.
        return date(year, 2, 28)


def _normalize_spaces(value: str) -> str:
    return " ".join((value or "").strip().split())


def _split_patient_name(full_name: str) -> tuple[str, str]:
    parts = _normalize_spaces(full_name).split(" ")
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def _validate_quick_patient_form(phone_number: str, patient_name: str, age_raw: str, gender: str, nic_number: str) -> tuple[list[str], int | None]:
    errors: list[str] = []

    if not PHONE_PATTERN.fullmatch(phone_number):
        errors.append("Phone number must be exactly 10 digits.")

    if not NAME_PATTERN.fullmatch(patient_name):
        errors.append("Patient name must be at least 2 characters and contain only letters and spaces.")

    age: int | None = None
    if not age_raw.isdigit():
        errors.append("Age must be a whole number between 0 and 120.")
    else:
        age = int(age_raw)
        if age < 0 or age > 120:
            errors.append("Age must be between 0 and 120.")

    if gender not in {"Male", "Female", "Other"}:
        errors.append("Please select a valid gender.")

    if nic_number and not NIC_PATTERN.fullmatch(nic_number):
        errors.append("NIC must be either 9 digits + V/X or 12 digits.")

    return errors, age


def _patient_quick_payload(row: dict) -> dict:
    first_name = (row.get("first_name") or "").strip()
    last_name = (row.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    return {
        "patient_id": row.get("patient_id"),
        "patient_name": full_name,
        "age": _calculate_age(row.get("date_of_birth")),
        "gender": row.get("gender") or "",
        "nic": row.get("nic_number") or "",
        "phone_number": row.get("phone_number") or "",
    }


def _load_patient_profile(patient_id: str) -> dict | None:
    patient_query = """
        SELECT p.patient_id, p.nic_number, p.first_name, p.last_name, p.date_of_birth,
               p.gender, p.phone_number, p.email, p.blood_group, p.address, p.city, p.district,
               mh.allergies, mh.chronic_conditions, mh.past_surgeries, mh.family_history
        FROM patients p
        LEFT JOIN medical_history mh ON mh.patient_id = p.patient_id
        WHERE p.patient_id = %s
        LIMIT 1
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(patient_query, (patient_id,))
        return cursor.fetchone()


def _load_vitals(patient_id: str) -> list[dict]:
    vitals_query = """
        SELECT v.blood_pressure, v.heart_rate, v.temperature, v.weight_kg, v.height_cm,
               v.record_date, COALESCE(u.full_name, u.username) AS recorded_by
        FROM patient_vitals v
        LEFT JOIN users u ON u.id = v.recorded_by
        WHERE v.patient_id = %s
        ORDER BY v.record_date DESC
        LIMIT 15
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(vitals_query, (patient_id,))
        return cursor.fetchall() or []


def _load_consultations(patient_id: str) -> list[dict]:
    consultations_query = """
        SELECT c.consultation_id, c.consultation_date, c.chief_complaint, c.diagnosis,
               c.clinical_notes, COALESCE(u.full_name, u.username) AS doctor_name
        FROM consultations c
        LEFT JOIN users u ON u.id = c.doctor_id
        WHERE c.patient_id = %s
        ORDER BY c.consultation_date DESC
        LIMIT 20
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(consultations_query, (patient_id,))
        return cursor.fetchall() or []


def _generate_patient_id() -> str:
    query = """
        SELECT MAX(CAST(SUBSTRING(patient_id, 5) AS UNSIGNED)) AS max_id
        FROM patients
        WHERE patient_id LIKE 'PAT-%'
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        row = cursor.fetchone() or {}

    max_id = row.get("max_id")
    if not max_id or max_id < PATIENT_ID_BASE:
        next_id = PATIENT_ID_BASE + 1
    else:
        next_id = max_id + 1
    return f"PAT-{next_id:04d}"


def _generate_patient_number() -> str:
    query = """
        SELECT MAX(CAST(SUBSTRING(patient_number, 5) AS UNSIGNED)) AS max_num
        FROM patients
        WHERE patient_number LIKE 'PAT-%'
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        row = cursor.fetchone() or {}

    max_num = row.get("max_num")
    if not max_num or max_num < PATIENT_NUMBER_BASE:
        next_num = PATIENT_NUMBER_BASE + 1
    else:
        next_num = int(max_num) + 1
    return f"PAT-{next_num:04d}"


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


def _fetch_patients(search: str | None, page: int) -> tuple[list[dict], int]:
    offset = (page - 1) * PAGE_SIZE
    filters = ""
    params: list = []

    if search:
        search_value = f"%{search}%"
        filters = (
            "WHERE patient_id LIKE %s OR nic_number LIKE %s OR phone_number LIKE %s "
            "OR first_name LIKE %s OR last_name LIKE %s OR CONCAT(first_name, ' ', last_name) LIKE %s"
        )
        params = [search_value] * 6

    count_query = f"SELECT COUNT(*) AS total FROM patients {filters}"
    data_query = f"""
        SELECT patient_id, nic_number, first_name, last_name, date_of_birth,
               gender, phone_number, blood_group
        FROM patients
        {filters}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(count_query, tuple(params))
        total = (cursor.fetchone() or {}).get("total", 0)
        cursor.execute(data_query, tuple(params + [PAGE_SIZE, offset]))
        patients = cursor.fetchall() or []

    return patients, int(total or 0)


@patients_bp.get("")
@login_required
@role_required(ALLOWED_ROLES)
def patient_directory():
    search = (request.args.get("search") or "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except ValueError:
        page = 1

    patients, total = _fetch_patients(search or None, page)
    total_pages = max(1, ceil(total / PAGE_SIZE))
    if page > total_pages:
        page = total_pages
        patients, total = _fetch_patients(search or None, page)

    return render_template(
        "patients/patient_directory.html",
        title="Patient Directory",
        active_page="patients",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        patients=patients,
        search=search,
        page=page,
        total_pages=total_pages,
        total=total,
        csrf_token=generate_csrf_token(),
    )


@patients_bp.get("/register")
@login_required
@role_required(ALLOWED_ROLES)
def patient_register():
    return render_template(
        "patients/patient_register_form.html",
        title="Patient Registration",
        active_page="patients",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        csrf_token=generate_csrf_token(),
    )


@patients_bp.get("/quick-lookup")
@login_required
@role_required(ALLOWED_ROLES)
def patient_quick_lookup():
    raw_phone = request.args.get("phone", "")
    phone_digits = re.sub(r"\D", "", raw_phone)

    if len(phone_digits) < 3:
        return jsonify(
            {
                "status": "idle",
                "message": "Enter at least 3 digits to search.",
                "patients": [],
            }
        )

    query = """
        SELECT patient_id, first_name, last_name, date_of_birth, gender, nic_number, phone_number
        FROM patients
        WHERE phone_number LIKE %s
        ORDER BY updated_at DESC
        LIMIT 10
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (f"%{phone_digits}%",))
        rows = cursor.fetchall() or []

    payload = [_patient_quick_payload(row) for row in rows]
    if len(payload) == 1:
        return jsonify(
            {
                "status": "single",
                "message": "Existing patient found.",
                "patients": payload,
            }
        )
    if len(payload) > 1:
        return jsonify(
            {
                "status": "multiple",
                "message": "Multiple patients found. Please select one.",
                "patients": payload,
            }
        )
    return jsonify(
        {
            "status": "none",
            "message": "New patient.",
            "patients": [],
        }
    )


@patients_bp.post("/register")
@login_required
@role_required(ALLOWED_ROLES)
def patient_register_submit():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("patients.patient_register"))

    phone_number = re.sub(r"\D", "", request.form.get("phone_number") or "")
    patient_name = _normalize_spaces(request.form.get("patient_name") or "")
    age_raw = (request.form.get("age") or "").strip()
    gender = (request.form.get("gender") or "").strip()
    nic_number = (request.form.get("nic_number") or "").strip().upper()
    existing_patient_id = (request.form.get("existing_patient_id") or "").strip()

    errors, age = _validate_quick_patient_form(phone_number, patient_name, age_raw, gender, nic_number)
    if errors or age is None:
        flash(errors[0] if errors else "Invalid input.", "error")
        return redirect(url_for("patients.patient_register"))

    date_of_birth = _estimate_dob_from_age(age)
    first_name, last_name = _split_patient_name(patient_name)

    duplicate_query = "SELECT patient_id FROM patients WHERE nic_number = %s LIMIT 1"
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        if nic_number:
            cursor.execute(duplicate_query, (nic_number,))
            nic_owner = cursor.fetchone()
        else:
            nic_owner = None

        if nic_owner and nic_owner.get("patient_id") != existing_patient_id:
            flash("A patient with this NIC already exists.", "error")
            return redirect(url_for("patients.patient_register"))

        if existing_patient_id:
            cursor.execute("SELECT patient_id FROM patients WHERE patient_id = %s LIMIT 1", (existing_patient_id,))
            existing_patient = cursor.fetchone()
            if not existing_patient:
                flash("Selected existing patient was not found.", "error")
                return redirect(url_for("patients.patient_register"))

            update_query = """
                UPDATE patients
                SET first_name = %s,
                    last_name = %s,
                    date_of_birth = %s,
                    gender = %s,
                    phone_number = %s,
                    nic_number = %s
                WHERE patient_id = %s
            """
            cursor.execute(
                update_query,
                (
                    first_name,
                    last_name,
                    date_of_birth,
                    gender,
                    phone_number,
                    nic_number or None,
                    existing_patient_id,
                ),
            )
            patient_id = existing_patient_id
            flash(f"Existing patient updated. ID: {patient_id}", "success")
        else:
            has_patient_number = _patients_has_column("patient_number")
            if has_patient_number:
                patient_number = _generate_patient_number()
                insert_query = """
                    INSERT INTO patients (
                        patient_number, nic_number, first_name, last_name, date_of_birth, gender, phone_number
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(
                    insert_query,
                    (
                        patient_number,
                        nic_number or None,
                        first_name,
                        last_name,
                        date_of_birth,
                        gender,
                        phone_number,
                    ),
                )
                patient_id = str(cursor.lastrowid)
            else:
                patient_id = _generate_patient_id()
                insert_query = """
                    INSERT INTO patients (
                        patient_id, nic_number, first_name, last_name, date_of_birth, gender, phone_number
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(
                    insert_query,
                    (
                        patient_id,
                        nic_number or None,
                        first_name,
                        last_name,
                        date_of_birth,
                        gender,
                        phone_number,
                    ),
                )
            flash(f"Patient registered successfully. ID: {patient_id}", "success")

    return redirect(url_for("patients.patient_directory", search=patient_id))


@patient_profile_bp.get("/<patient_id>")
@login_required
@role_required(PROFILE_VIEW_ROLES)
def patient_profile(patient_id: str):
    patient = _load_patient_profile(patient_id)
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("patients.patient_directory"))

    vitals = _load_vitals(patient_id)
    consultations = _load_consultations(patient_id)
    latest_vitals = vitals[0] if vitals else None
    patient_age = _calculate_age(patient.get("date_of_birth"))

    return render_template(
        "patients/patient_profile.html",
        title="Patient Profile",
        active_page="patients",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        patient=patient,
        patient_age=patient_age,
        vitals=vitals,
        latest_vitals=latest_vitals,
        consultations=consultations,
        csrf_token=generate_csrf_token(),
    )


@patient_profile_bp.post("/<patient_id>/history")
@login_required
@role_required(PROFILE_EDIT_ROLES)
def patient_update_history(patient_id: str):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("patient_profile.patient_profile", patient_id=patient_id))

    allergies = (request.form.get("allergies") or "").strip()
    chronic_conditions = (request.form.get("chronic_conditions") or "").strip()
    past_surgeries = (request.form.get("past_surgeries") or "").strip()
    family_history = (request.form.get("family_history") or "").strip()

    upsert_query = """
        INSERT INTO medical_history (patient_id, allergies, chronic_conditions, past_surgeries, family_history)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            allergies = VALUES(allergies),
            chronic_conditions = VALUES(chronic_conditions),
            past_surgeries = VALUES(past_surgeries),
            family_history = VALUES(family_history)
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            upsert_query,
            (patient_id, allergies or None, chronic_conditions or None, past_surgeries or None, family_history or None),
        )

    flash("Medical history updated.", "success")
    return redirect(url_for("patient_profile.patient_profile", patient_id=patient_id))


@patient_profile_bp.post("/<patient_id>/vitals")
@login_required
@role_required(PROFILE_EDIT_ROLES)
def patient_add_vitals(patient_id: str):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("patient_profile.patient_profile", patient_id=patient_id))

    blood_pressure = (request.form.get("blood_pressure") or "").strip()
    heart_rate = (request.form.get("heart_rate") or "").strip()
    temperature = (request.form.get("temperature") or "").strip()
    weight_kg = (request.form.get("weight_kg") or "").strip()
    height_cm = (request.form.get("height_cm") or "").strip()

    if not any([blood_pressure, heart_rate, temperature, weight_kg, height_cm]):
        flash("Enter at least one vital sign.", "error")
        return redirect(url_for("patient_profile.patient_profile", patient_id=patient_id))

    insert_query = """
        INSERT INTO patient_vitals (
            patient_id, blood_pressure, heart_rate, temperature, weight_kg, height_cm, record_date, recorded_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            insert_query,
            (
                patient_id,
                blood_pressure or None,
                heart_rate or None,
                temperature or None,
                weight_kg or None,
                height_cm or None,
                session.get("user_id"),
            ),
        )

    flash("Vitals recorded.", "success")
    return redirect(url_for("patient_profile.patient_profile", patient_id=patient_id))


@patient_profile_bp.post("/<patient_id>/consultation")
@login_required
@role_required(PROFILE_EDIT_ROLES)
def patient_add_consultation(patient_id: str):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("patient_profile.patient_profile", patient_id=patient_id))

    chief_complaint = (request.form.get("chief_complaint") or "").strip()
    diagnosis = (request.form.get("diagnosis") or "").strip()
    clinical_notes = (request.form.get("clinical_notes") or "").strip()

    if not chief_complaint:
        flash("Chief complaint is required.", "error")
        return redirect(url_for("patient_profile.patient_profile", patient_id=patient_id))

    insert_query = """
        INSERT INTO consultations (patient_id, doctor_id, consultation_date, chief_complaint, clinical_notes, diagnosis)
        VALUES (%s, %s, NOW(), %s, %s, %s)
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            insert_query,
            (patient_id, session.get("user_id"), chief_complaint, clinical_notes or None, diagnosis or None),
        )

    flash("Consultation note added.", "success")
    return redirect(url_for("patient_profile.patient_profile", patient_id=patient_id))
