from __future__ import annotations

import secrets
import string

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from medicore.db.connection import get_db_cursor
from medicore.security.passwords import hash_password
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")

ALLOWED_ROLES = ["SuperAdmin", "CenterAdmin"]


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*?"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _load_roles():
    query = "SELECT id, role_name FROM roles ORDER BY role_name"
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _load_staff():
    query = """
        SELECT u.id, u.full_name, u.email, u.phone_number, u.is_active,
               r.role_name
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        ORDER BY u.full_name
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


@staff_bp.get("")
@login_required
@role_required(ALLOWED_ROLES)
def staff_list():
    return render_template(
        "staff/staff_list.html",
        title="Staff Management",
        active_page="staff",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        staff=_load_staff(),
        roles=_load_roles(),
        csrf_token=generate_csrf_token(),
    )


@staff_bp.post("/add")
@login_required
@role_required(ALLOWED_ROLES)
def staff_add():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("staff.staff_list"))

    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip()
    phone = (request.form.get("phone_number") or "").strip()
    role_id = request.form.get("role_id")

    if not all([full_name, email, phone, role_id]):
        flash("All staff fields are required.", "error")
        return redirect(url_for("staff.staff_list"))

    temp_password = _generate_temp_password()
    password_hash = hash_password(temp_password)

    insert_query = """
        INSERT INTO users (full_name, email, phone_number, role_id, username, password_hash, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, 1)
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(insert_query, (full_name, email, phone, role_id, email, password_hash))

    flash(
        f"Staff created. Temporary password: {temp_password}. Share securely and reset after first login.",
        "success",
    )
    return redirect(url_for("staff.staff_list"))


@staff_bp.post("/edit/<int:staff_id>")
@login_required
@role_required(ALLOWED_ROLES)
def staff_edit(staff_id: int):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("staff.staff_list"))

    full_name = (request.form.get("full_name") or "").strip()
    email = (request.form.get("email") or "").strip()
    phone = (request.form.get("phone_number") or "").strip()
    role_id = request.form.get("role_id")

    update_query = """
        UPDATE users
        SET full_name = %s, email = %s, phone_number = %s, role_id = %s
        WHERE id = %s
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(update_query, (full_name, email, phone, role_id, staff_id))

    flash("Staff updated.", "success")
    return redirect(url_for("staff.staff_list"))


@staff_bp.post("/toggle-status/<int:staff_id>")
@login_required
@role_required(ALLOWED_ROLES)
def staff_toggle_status(staff_id: int):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("staff.staff_list"))

    toggle_query = """
        UPDATE users
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
        WHERE id = %s
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(toggle_query, (staff_id,))

    flash("Staff status updated.", "success")
    return redirect(url_for("staff.staff_list"))
