from __future__ import annotations

import re
import secrets

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from medicore.db.connection import get_db_cursor
from medicore.security.passwords import hash_password
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


def _normalize_name(value: str) -> str:
    return " ".join((value or "").strip().split())


def _split_name(full_name: str) -> tuple[str, str]:
    parts = _normalize_name(full_name).split(" ")
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def _sanitize_code(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", (value or "").strip()).upper()


def _parse_fee(value: str) -> float:
    try:
        parsed = float((value or "0").strip())
        return max(0.0, parsed)
    except Exception:
        return 0.0


def _load_doctors_for_settings() -> list[dict]:
    query = """
        SELECT d.doctor_id,
               d.doctor_name,
               d.doctor_code,
               d.specialization,
               d.doctor_fee,
               d.hospital_fee,
               d.is_active,
               u.username,
               u.email
        FROM doctors d
        LEFT JOIN users u ON u.user_id = d.doctor_id
        ORDER BY d.doctor_name ASC
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
               COALESCE(u.full_name, u.email) AS user_name
        FROM audit_logs a
        LEFT JOIN users u ON u.user_id = a.user_id
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


@settings_bp.get("/doctors")
@login_required
@role_required(ALLOWED_ROLES)
def doctor_management_dashboard():
    return render_template(
        "settings/doctor_management.html",
        title="Doctor Management",
        active_page="settings",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        doctors=_load_doctors_for_settings(),
        csrf_token=generate_csrf_token(),
    )


@settings_bp.post("/doctors/add")
@login_required
@role_required(ALLOWED_ROLES)
def add_doctor():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.doctor_management_dashboard"))

    doctor_name = _normalize_name(request.form.get("doctor_name") or "")
    doctor_code = _sanitize_code(request.form.get("doctor_code") or "")
    specialization = _normalize_name(request.form.get("specialization") or "")
    doctor_fee = _parse_fee(request.form.get("doctor_fee") or "0")
    hospital_fee = _parse_fee(request.form.get("hospital_fee") or "0")

    if not doctor_name or len(doctor_name) < 2:
        flash("Doctor name is required.", "error")
        return redirect(url_for("settings.doctor_management_dashboard"))
    if not doctor_code:
        flash("Doctor code is required.", "error")
        return redirect(url_for("settings.doctor_management_dashboard"))

    first_name, last_name = _split_name(doctor_name)
    username = f"dr_{doctor_code.lower()}"
    email = f"{username}@medicore.local"
    password_seed = secrets.token_urlsafe(16)
    password_hash = hash_password(password_seed)

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("SELECT 1 FROM doctors WHERE doctor_code = %s LIMIT 1", (doctor_code,))
        if cursor.fetchone():
            flash("Doctor code already exists.", "error")
            return redirect(url_for("settings.doctor_management_dashboard"))

        cursor.execute("SELECT id FROM roles WHERE role_name = 'Doctor' LIMIT 1")
        role_row = cursor.fetchone() or {}
        role_id = role_row.get("id")

        cursor.execute(
            """
            INSERT INTO users (
                email, password_hash, first_name, last_name, username,
                role, role_id, status, is_active, full_name
            ) VALUES (%s, %s, %s, %s, %s, 'Doctor', %s, 'Active', 1, %s)
            """,
            (email, password_hash, first_name, last_name, username, role_id, doctor_name),
        )
        doctor_user_id = int(cursor.lastrowid)

        cursor.execute(
            """
            INSERT INTO doctors (
                doctor_id, doctor_name, doctor_code, specialization,
                doctor_fee, hospital_fee, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, 1)
            """,
            (
                doctor_user_id,
                doctor_name,
                doctor_code,
                specialization or None,
                doctor_fee,
                hospital_fee,
            ),
        )

    flash("Doctor added successfully.", "success")
    return redirect(url_for("settings.doctor_management_dashboard"))


@settings_bp.post("/doctors/edit/<int:doctor_id>")
@login_required
@role_required(ALLOWED_ROLES)
def edit_doctor(doctor_id: int):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.doctor_management_dashboard"))

    doctor_name = _normalize_name(request.form.get("doctor_name") or "")
    specialization = _normalize_name(request.form.get("specialization") or "")
    doctor_fee = _parse_fee(request.form.get("doctor_fee") or "0")
    hospital_fee = _parse_fee(request.form.get("hospital_fee") or "0")

    if not doctor_name or len(doctor_name) < 2:
        flash("Doctor name is required.", "error")
        return redirect(url_for("settings.doctor_management_dashboard"))

    first_name, last_name = _split_name(doctor_name)
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            """
            UPDATE doctors
            SET doctor_name = %s,
                specialization = %s,
                doctor_fee = %s,
                hospital_fee = %s,
                updated_at = NOW()
            WHERE doctor_id = %s
            """,
            (doctor_name, specialization or None, doctor_fee, hospital_fee, doctor_id),
        )
        cursor.execute(
            """
            UPDATE users
            SET first_name = %s,
                last_name = %s,
                full_name = %s
            WHERE user_id = %s
            """,
            (first_name, last_name, doctor_name, doctor_id),
        )

    flash("Doctor updated.", "success")
    return redirect(url_for("settings.doctor_management_dashboard"))


@settings_bp.post("/doctors/toggle/<int:doctor_id>")
@login_required
@role_required(ALLOWED_ROLES)
def toggle_doctor(doctor_id: int):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.doctor_management_dashboard"))

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("SELECT is_active FROM doctors WHERE doctor_id = %s LIMIT 1", (doctor_id,))
        row = cursor.fetchone()
        if not row:
            flash("Doctor not found.", "error")
            return redirect(url_for("settings.doctor_management_dashboard"))

        next_active = 0 if int(row.get("is_active", 0)) == 1 else 1
        next_status = "Active" if next_active == 1 else "Inactive"

        cursor.execute(
            "UPDATE doctors SET is_active = %s, updated_at = NOW() WHERE doctor_id = %s",
            (next_active, doctor_id),
        )
        cursor.execute(
            "UPDATE users SET is_active = %s, status = %s WHERE user_id = %s",
            (next_active, next_status, doctor_id),
        )

    flash("Doctor status updated.", "success")
    return redirect(url_for("settings.doctor_management_dashboard"))


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


# ======================== SERVICE MANAGEMENT ========================


def _load_service_categories() -> list[dict]:
    """Load all active service categories ordered by display_order."""
    query = """
        SELECT category_id, category_name, icon_class, display_order, is_active, description
        FROM service_categories
        WHERE is_active = TRUE
        ORDER BY display_order ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _load_all_service_categories() -> list[dict]:
    """Load all service categories (active and inactive) for management."""
    query = """
        SELECT category_id, category_name, icon_class, display_order, is_active, description
        FROM service_categories
        ORDER BY display_order ASC, category_name ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _load_service_items_for_category(category_id: int) -> list[dict]:
    """Load all service items for a given category."""
    query = """
        SELECT item_id, item_code, item_name, category_id, price, description, is_active, display_order
        FROM service_items
        WHERE category_id = %s
        ORDER BY display_order ASC, item_name ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (category_id,))
        return cursor.fetchall() or []


@settings_bp.get("/services")
@login_required
@role_required(ALLOWED_ROLES)
def services_management_dashboard():
    """Main services management dashboard."""
    categories = _load_all_service_categories()

    # Load all items with their category name + linked inventory info
    items_query = """
        SELECT si.item_id, si.item_code, si.item_name, si.category_id,
               si.price, si.description, si.is_active, si.display_order,
               si.linked_inventory_item_id,
               sc.category_name,
               inv.item_name AS linked_inv_name,
               inv.quantity_on_hand AS linked_inv_stock
        FROM service_items si
        INNER JOIN service_categories sc ON sc.category_id = si.category_id
        LEFT JOIN inventory_items inv ON inv.item_id = si.linked_inventory_item_id
        ORDER BY sc.display_order ASC, si.display_order ASC, si.item_name ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(items_query)
        all_items = cursor.fetchall() or []

    return render_template(
        "settings/services_management.html",
        title="Services Management",
        active_page="settings",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        categories=categories,
        all_items=all_items,
        csrf_token=generate_csrf_token(),
    )


@settings_bp.get("/api/inventory/search")
@login_required
@role_required(ALLOWED_ROLES)
def api_search_inventory():
    """JSON API: search inventory items."""
    q = (request.args.get("q") or "").strip()
    usage_filter = request.args.get("usage", "all")  # 'sale', 'both', or 'all'

    base_query = """
        SELECT item_id, item_name, item_code, selling_price, quantity_on_hand, unit, usage_mode
        FROM inventory_items
        WHERE status = 'Active'
    """
    params: list = []

    if usage_filter in ("sale", "both"):
        base_query += " AND usage_mode IN ('Sale', 'Both')"

    if q:
        base_query += " AND (item_name LIKE %s OR item_code LIKE %s)"
        params.extend([f"%{q}%", f"%{q}%"])

    base_query += " ORDER BY item_name ASC LIMIT 30"

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(base_query, tuple(params))
        items = cursor.fetchall() or []

    # Convert Decimal to float for JSON serialisation
    for item in items:
        if item.get("selling_price") is not None:
            item["selling_price"] = float(item["selling_price"])

    return jsonify({"ok": True, "items": items})




@settings_bp.post("/services/category/add")
@login_required
@role_required(ALLOWED_ROLES)
def add_service_category():
    """Add a new service category."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    category_name = _normalize_name(request.form.get("category_name") or "")
    icon_class = (request.form.get("icon_class") or "").strip()
    description = (request.form.get("description") or "").strip()

    if not category_name or len(category_name) < 2:
        flash("Category name is required.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("SELECT 1 FROM service_categories WHERE category_name = %s LIMIT 1", (category_name,))
        if cursor.fetchone():
            flash("Category name already exists.", "error")
            return redirect(url_for("settings.services_management_dashboard"))

        cursor.execute(
            "SELECT MAX(display_order) as max_order FROM service_categories"
        )
        result = cursor.fetchone() or {}
        next_order = (result.get("max_order") or 0) + 1

        cursor.execute(
            """
            INSERT INTO service_categories (category_name, icon_class, display_order, is_active, description)
            VALUES (%s, %s, %s, TRUE, %s)
            """,
            (category_name, icon_class or None, next_order, description or None),
        )

    flash("Service category added successfully.", "success")
    return redirect(url_for("settings.services_management_dashboard"))


@settings_bp.post("/services/category/edit/<int:category_id>")
@login_required
@role_required(ALLOWED_ROLES)
def edit_service_category(category_id: int):
    """Edit a service category."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    category_name = _normalize_name(request.form.get("category_name") or "")
    icon_class = (request.form.get("icon_class") or "").strip()
    description = (request.form.get("description") or "").strip()

    if not category_name or len(category_name) < 2:
        flash("Category name is required.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            """
            UPDATE service_categories
            SET category_name = %s, icon_class = %s, description = %s, updated_at = NOW()
            WHERE category_id = %s
            """,
            (category_name, icon_class or None, description or None, category_id),
        )

    flash("Service category updated.", "success")
    return redirect(url_for("settings.services_management_dashboard"))


@settings_bp.post("/services/category/toggle/<int:category_id>")
@login_required
@role_required(ALLOWED_ROLES)
def toggle_service_category(category_id: int):
    """Toggle category active/inactive status."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            """
            UPDATE service_categories
            SET is_active = NOT is_active, updated_at = NOW()
            WHERE category_id = %s
            """,
            (category_id,),
        )

    flash("Category status updated.", "success")
    return redirect(url_for("settings.services_management_dashboard"))


@settings_bp.post("/services/item/add")
@login_required
@role_required(ALLOWED_ROLES)
def add_service_item():
    """Add a new service item."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    item_code = _sanitize_code(request.form.get("item_code") or "")
    item_name = _normalize_name(request.form.get("item_name") or "")
    category_id = request.form.get("category_id") or ""
    price = _parse_fee(request.form.get("price") or "0")
    description = (request.form.get("description") or "").strip()

    if not item_code:
        flash("Item code is required.", "error")
        return redirect(url_for("settings.services_management_dashboard"))
    if not item_name or len(item_name) < 2:
        flash("Item name is required.", "error")
        return redirect(url_for("settings.services_management_dashboard"))
    if not category_id:
        flash("Category is required.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    try:
        category_id = int(category_id)
    except ValueError:
        flash("Invalid category selected.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("SELECT 1 FROM service_items WHERE item_code = %s LIMIT 1", (item_code,))
        if cursor.fetchone():
            flash("Item code already exists.", "error")
            return redirect(url_for("settings.services_management_dashboard"))

        cursor.execute("SELECT 1 FROM service_categories WHERE category_id = %s LIMIT 1", (category_id,))
        if not cursor.fetchone():
            flash("Invalid category selected.", "error")
            return redirect(url_for("settings.services_management_dashboard"))

        cursor.execute(
            "SELECT MAX(display_order) as max_order FROM service_items WHERE category_id = %s",
            (category_id,),
        )
        result = cursor.fetchone() or {}
        next_order = (result.get("max_order") or 0) + 1

        cursor.execute(
            """
            INSERT INTO service_items (item_code, item_name, category_id, price, description, is_active, display_order)
            VALUES (%s, %s, %s, %s, %s, TRUE, %s)
            """,
            (item_code, item_name, category_id, price, description or None, next_order),
        )

    flash("Service item added successfully.", "success")
    return redirect(url_for("settings.services_management_dashboard"))


@settings_bp.post("/services/item/edit/<int:item_id>")
@login_required
@role_required(ALLOWED_ROLES)
def edit_service_item(item_id: int):
    """Edit a service item."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    item_name = _normalize_name(request.form.get("item_name") or "")
    category_id = request.form.get("category_id") or ""
    price = _parse_fee(request.form.get("price") or "0")
    description = (request.form.get("description") or "").strip()

    if not item_name or len(item_name) < 2:
        flash("Item name is required.", "error")
        return redirect(url_for("settings.services_management_dashboard"))
    if not category_id:
        flash("Category is required.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    try:
        category_id = int(category_id)
    except ValueError:
        flash("Invalid category selected.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("SELECT 1 FROM service_categories WHERE category_id = %s LIMIT 1", (category_id,))
        if not cursor.fetchone():
            flash("Invalid category selected.", "error")
            return redirect(url_for("settings.services_management_dashboard"))

        cursor.execute(
            """
            UPDATE service_items
            SET item_name = %s, category_id = %s, price = %s, description = %s, updated_at = NOW()
            WHERE item_id = %s
            """,
            (item_name, category_id, price, description or None, item_id),
        )

    flash("Service item updated.", "success")
    return redirect(url_for("settings.services_management_dashboard"))


@settings_bp.post("/services/item/toggle/<int:item_id>")
@login_required
@role_required(ALLOWED_ROLES)
def toggle_service_item(item_id: int):
    """Toggle item active/inactive status."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.services_management_dashboard"))

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            """
            UPDATE service_items
            SET is_active = NOT is_active, updated_at = NOW()
            WHERE item_id = %s
            """,
            (item_id,),
        )

    flash("Item status updated.", "success")
    return redirect(url_for("settings.services_management_dashboard"))

@settings_bp.get("/inventory/mapping/<int:service_id>")
@login_required
@role_required(ALLOWED_ROLES)
def service_inventory_mapping(service_id: int):
    """View and manage inventory mapping for a service."""
    service_query = "SELECT item_id, item_name, item_code FROM service_items WHERE item_id = %s"
    items_query = "SELECT item_id, item_name, item_code, quantity_on_hand, unit FROM inventory_items WHERE status = 'Active' ORDER BY item_name"
    mapping_query = """
        SELECT m.mapping_id, m.inventory_item_id, m.quantity_required, i.item_name, i.unit
        FROM service_inventory_mapping m
        JOIN inventory_items i ON m.inventory_item_id = i.item_id
        WHERE m.service_item_id = %s
    """
    
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(service_query, (service_id,))
        service = cursor.fetchone()
        if not service:
            flash("Service not found.", "error")
            return redirect(url_for("settings.services_management_dashboard"))
            
        cursor.execute(items_query)
        inventory_items = cursor.fetchall() or []
        
        cursor.execute(mapping_query, (service_id,))
        mappings = cursor.fetchall() or []
        
    return render_template(
        "settings/service_inventory_mapping.html",
        title=f"Inventory Mapping: {service['item_name']}",
        active_page="settings",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        service=service,
        inventory_items=inventory_items,
        mappings=mappings,
        csrf_token=generate_csrf_token(),
    )


@settings_bp.post("/inventory/mapping/add/<int:service_id>")
@login_required
@role_required(ALLOWED_ROLES)
def add_service_mapping(service_id: int):
    """Add a new inventory requirement to a service."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("settings.service_inventory_mapping", service_id=service_id))
        
    inventory_item_id = request.form.get("inventory_item_id")
    quantity = request.form.get("quantity")
    stage = request.form.get("usage_stage", "on_completion")
    is_required = 1 if request.form.get("is_required") == "on" else 0
    
    query = """
        INSERT INTO service_inventory_mapping 
        (service_item_id, inventory_item_id, quantity_required, usage_stage, is_required)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            quantity_required = VALUES(quantity_required),
            usage_stage = VALUES(usage_stage),
            is_required = VALUES(is_required)
    """
    
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (service_id, inventory_item_id, quantity, stage, is_required))
        
    flash("Inventory mapping updated for this service.", "success")
    return redirect(url_for("settings.service_inventory_mapping", service_id=service_id))

@settings_bp.post("/inventory/mapping/delete/<int:mapping_id>")
@login_required
@role_required(ALLOWED_ROLES)
def delete_service_mapping(mapping_id: int):
    """Remove an inventory requirement from a service."""
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return jsonify({"ok": False, "message": "Invalid CSRF"}), 400
        
    service_id = request.args.get("service_id")
    
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("DELETE FROM service_inventory_mapping WHERE mapping_id = %s", (mapping_id,))
        
    flash("Mapping removed.", "success")
    if service_id:
        return redirect(url_for("settings.service_inventory_mapping", service_id=service_id))
    return redirect(url_for("settings.services_management_dashboard"))
