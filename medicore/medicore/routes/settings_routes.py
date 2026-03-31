from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from medicore.db.connection import get_db_cursor
from medicore.security.audit import log_audit_action
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

ALLOWED_ROLES = ["SuperAdmin", "CenterAdmin"]
SUPERADMIN_ONLY = ["SuperAdmin"]

SETTINGS_FIELDS = {
    "clinic_name": "Clinic Name",
    "clinic_address": "Clinic Address",
    "clinic_contact": "Clinic Contact",
    "vat_percentage": "VAT Percentage",
    "sscl_percentage": "SSCL Percentage",
    "invoice_notes": "Default Invoice Notes",
    "sms_gateway_active": "SMS Gateway Active",
    "whatsapp_gateway_active": "WhatsApp Gateway Active",
}


def _load_settings() -> dict:
    query = "SELECT setting_key, setting_value FROM system_settings"
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        rows = cursor.fetchall() or []
    return {row["setting_key"]: row["setting_value"] for row in rows}


def _save_setting(cursor, key: str, value: str, description: str | None = None):
    query = """
        INSERT INTO system_settings (setting_key, setting_value, description)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value), description = VALUES(description)
    """
    cursor.execute(query, (key, value, description))


def _load_departments() -> list[dict]:
    query = """
        SELECT department_id, department_name, description, status
        FROM departments
        ORDER BY department_name ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _load_tax_rules() -> list[dict]:
    query = """
        SELECT tax_id, tax_name, percentage, is_active
        FROM tax_rules
        ORDER BY tax_name ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


@settings_bp.get("")
@login_required
@role_required(ALLOWED_ROLES)
def settings_dashboard():
    settings = _load_settings()
    return render_template(
        "settings/settings_dashboard.html",
        title="System Settings",
        active_page="settings",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        settings=settings,
        csrf_token=generate_csrf_token(),
    )


@settings_bp.post("/update")
@login_required
@role_required(ALLOWED_ROLES)
def settings_update():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.settings_dashboard"))

    current_settings = _load_settings()
    updated_values = {}

    for key in SETTINGS_FIELDS:
        if key in ["sms_gateway_active", "whatsapp_gateway_active"]:
            value = "true" if request.form.get(key) == "on" else "false"
        else:
            value = (request.form.get(key) or "").strip()
        updated_values[key] = value

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        for key, value in updated_values.items():
            _save_setting(cursor, key, value, SETTINGS_FIELDS.get(key))

    log_audit_action(
        action_type="UPDATE_SETTINGS",
        table_affected="system_settings",
        record_id=None,
        old_values=current_settings,
        new_values=updated_values,
        async_log=True,
    )

    flash("Settings updated successfully.", "success")
    return redirect(url_for("settings.settings_dashboard"))


@settings_bp.get("/audit")
@login_required
@role_required(["SuperAdmin"])
def audit_log_view():
    action_filter = request.args.get("action_type")
    user_filter = request.args.get("user_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = """
        SELECT a.log_id, a.user_id, a.action_type, a.table_affected, a.record_id,
               a.old_values, a.new_values, a.ip_address, a.created_at,
               COALESCE(u.full_name, u.username) AS user_name
        FROM audit_logs a
        LEFT JOIN users u ON u.id = a.user_id
        WHERE 1=1
    """
    params = []

    if action_filter:
        query += " AND a.action_type = %s"
        params.append(action_filter)
    if user_filter:
        query += " AND a.user_id = %s"
        params.append(user_filter)
    if start_date:
        query += " AND a.created_at >= %s"
        params.append(start_date)
    if end_date:
        query += " AND a.created_at <= %s"
        params.append(end_date)

    query += " ORDER BY a.created_at DESC LIMIT 300"

    types_query = "SELECT DISTINCT action_type FROM audit_logs ORDER BY action_type"

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, tuple(params))
        logs = cursor.fetchall() or []
        cursor.execute(types_query)
        action_types = [row["action_type"] for row in cursor.fetchall() or []]

    return render_template(
        "settings/audit_log_view.html",
        title="Audit Logs",
        active_page="settings",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        logs=logs,
        action_types=action_types,
        filters={
            "action_type": action_filter or "",
            "user_id": user_filter or "",
            "start_date": start_date or "",
            "end_date": end_date or "",
        },
        csrf_token=generate_csrf_token(),
    )


@settings_bp.get("/tax-departments")
@login_required
@role_required(SUPERADMIN_ONLY)
def tax_departments_dashboard():
    return render_template(
        "settings/tax_and_departments.html",
        title="Tax & Departments",
        active_page="settings",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        departments=_load_departments(),
        tax_rules=_load_tax_rules(),
        csrf_token=generate_csrf_token(),
    )


@settings_bp.post("/departments/add")
@login_required
@role_required(SUPERADMIN_ONLY)
def add_department():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.tax_departments_dashboard"))

    name = (request.form.get("department_name") or "").strip()
    description = (request.form.get("description") or "").strip()
    if not name:
        flash("Department name is required.", "error")
        return redirect(url_for("settings.tax_departments_dashboard"))

    insert_query = """
        INSERT INTO departments (department_name, description, status)
        VALUES (%s, %s, 'Active')
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(insert_query, (name, description or None))

    flash("Department added.", "success")
    return redirect(url_for("settings.tax_departments_dashboard"))


@settings_bp.post("/departments/toggle/<int:department_id>")
@login_required
@role_required(SUPERADMIN_ONLY)
def toggle_department(department_id: int):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.tax_departments_dashboard"))

    query = """
        UPDATE departments
        SET status = CASE WHEN status = 'Active' THEN 'Inactive' ELSE 'Active' END
        WHERE department_id = %s
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (department_id,))

    flash("Department status updated.", "success")
    return redirect(url_for("settings.tax_departments_dashboard"))


@settings_bp.post("/tax/add")
@login_required
@role_required(SUPERADMIN_ONLY)
def add_tax_rule():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.tax_departments_dashboard"))

    name = (request.form.get("tax_name") or "").strip()
    percentage = (request.form.get("percentage") or "").strip()
    if not name or not percentage:
        flash("Tax name and percentage are required.", "error")
        return redirect(url_for("settings.tax_departments_dashboard"))

    insert_query = """
        INSERT INTO tax_rules (tax_name, percentage, is_active)
        VALUES (%s, %s, 1)
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(insert_query, (name, percentage))

    flash("Tax rule added.", "success")
    return redirect(url_for("settings.tax_departments_dashboard"))


@settings_bp.post("/tax/toggle/<int:tax_id>")
@login_required
@role_required(SUPERADMIN_ONLY)
def toggle_tax_rule(tax_id: int):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.tax_departments_dashboard"))

    query = """
        UPDATE tax_rules
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
        WHERE tax_id = %s
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (tax_id,))

    flash("Tax rule status updated.", "success")
    return redirect(url_for("settings.tax_departments_dashboard"))
