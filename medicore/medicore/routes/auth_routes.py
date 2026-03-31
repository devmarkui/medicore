from __future__ import annotations

import base64
import io
from http import HTTPStatus

import pyotp
import qrcode
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from medicore.db.connection import get_db_cursor
from medicore.security.passwords import verify_password
from medicore.security.rbac import login_required
from medicore.security.session_security import destroy_session, rotate_session
from medicore.security.web import generate_csrf_token, validate_csrf_token

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _generate_qr_data_uri(otp_uri: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=6, border=4)
    qr.add_data(otp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


@auth_bp.get("/login")
def login():
    return render_template("auth/login.html", csrf_token=generate_csrf_token())


@auth_bp.post("/login")
def login_post():
    if not validate_csrf_token():
        flash("Invalid request token. Please try again.", "error")
        return redirect(url_for("auth.login"))

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        flash("Username and password are required.", "error")
        return redirect(url_for("auth.login"))

    query = """
        SELECT u.id, u.username, u.password_hash, u.is_2fa_enabled, r.role_name
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        WHERE u.username = %s AND u.is_active = 1
        LIMIT 1
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (username,))
        user = cursor.fetchone()

    if not user or not verify_password(user["password_hash"], password):
        flash("Invalid credentials.", "error")
        return redirect(url_for("auth.login"))

    if user.get("is_2fa_enabled"):
        session.clear()
        session["pending_2fa"] = {
            "user_id": int(user["id"]),
            "username": user["username"],
            "role_name": user["role_name"],
        }
        flash("Enter your 2FA code to finish signing in.", "info")
        return redirect(url_for("auth.verify_2fa_form"))

    rotate_session(
        user_id=user["id"],
        username=user["username"],
        role_name=user["role_name"],
    )
    flash("Login successful.", "success")
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.get("/setup-2fa")
@login_required
def setup_2fa():
    user_id = session.get("user_id")
    query = """
        SELECT id, username, two_factor_secret, is_2fa_enabled
        FROM users
        WHERE id = %s
        LIMIT 1
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
        if not user:
            flash("Unable to load your account.", "error")
            return redirect(url_for("dashboard.dashboard"))

        secret = user.get("two_factor_secret") or pyotp.random_base32()
        if not user.get("two_factor_secret"):
            cursor.execute(
                "UPDATE users SET two_factor_secret = %s WHERE id = %s",
                (secret, user_id),
            )

    totp = pyotp.TOTP(secret)
    otp_uri = totp.provisioning_uri(name=user["username"], issuer_name="MediCore")
    qr_data_uri = _generate_qr_data_uri(otp_uri)

    return render_template(
        "auth/setup_2fa.html",
        title="Setup Two-Factor Authentication",
        active_page="settings",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        qr_code_data=qr_data_uri,
        secret=secret,
        otp_uri=otp_uri,
        is_enabled=bool(user.get("is_2fa_enabled")),
        csrf_token=generate_csrf_token(),
    )


@auth_bp.get("/verify-2fa")
def verify_2fa_form():
    if session.get("authenticated"):
        return redirect(url_for("dashboard.dashboard"))
    if not session.get("pending_2fa"):
        flash("Please sign in to continue.", "error")
        return redirect(url_for("auth.login"))
    return render_template(
        "auth/verify_2fa.html",
        csrf_token=generate_csrf_token(),
    )


@auth_bp.post("/verify-2fa")
def verify_2fa():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        if session.get("authenticated"):
            return redirect(url_for("auth.setup_2fa"))
        return redirect(url_for("auth.verify_2fa_form"))

    token = (request.form.get("token") or "").strip()
    context = (request.form.get("context") or "login").lower()

    if not token:
        flash("Enter the 6-digit code.", "error")
        if context == "enable":
            return redirect(url_for("auth.setup_2fa"))
        return redirect(url_for("auth.verify_2fa_form"))

    if context == "enable":
        if not session.get("authenticated"):
            flash("Sign in to configure 2FA.", "error")
            return redirect(url_for("auth.login"))
        user_id = session.get("user_id")
        query = """
            SELECT two_factor_secret
            FROM users
            WHERE id = %s
            LIMIT 1
        """
        with get_db_cursor(dictionary=True) as (_conn, cursor):
            cursor.execute(query, (user_id,))
            result = cursor.fetchone()
            secret = (result or {}).get("two_factor_secret")
            if not secret:
                flash("Generate a QR code first.", "error")
                return redirect(url_for("auth.setup_2fa"))

            totp = pyotp.TOTP(secret)
            if not totp.verify(token, valid_window=1):
                flash("Invalid authentication code.", "error")
                return redirect(url_for("auth.setup_2fa"))

            cursor.execute(
                "UPDATE users SET is_2fa_enabled = 1 WHERE id = %s",
                (user_id,),
            )

        flash("Two-factor authentication enabled.", "success")
        return redirect(url_for("auth.setup_2fa"))

    pending = session.get("pending_2fa")
    if not pending:
        flash("Session expired. Please sign in again.", "error")
        return redirect(url_for("auth.login"))

    query = """
        SELECT two_factor_secret
        FROM users
        WHERE id = %s AND is_2fa_enabled = 1
        LIMIT 1
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (pending["user_id"],))
        user_secret = cursor.fetchone()

    secret = (user_secret or {}).get("two_factor_secret")
    if not secret:
        flash("Two-factor authentication is not configured for this account.", "error")
        session.pop("pending_2fa", None)
        return redirect(url_for("auth.login"))

    totp = pyotp.TOTP(secret)
    if not totp.verify(token, valid_window=1):
        flash("Invalid authentication code.", "error")
        return redirect(url_for("auth.verify_2fa_form"))

    rotate_session(
        user_id=pending["user_id"],
        username=pending["username"],
        role_name=pending["role_name"],
    )
    session.pop("pending_2fa", None)
    flash("Login successful.", "success")
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.post("/logout")
def logout():
    if not validate_csrf_token():
        return ("Invalid CSRF token", HTTPStatus.BAD_REQUEST)

    destroy_session()
    flash("You have been logged out securely.", "success")
    return redirect(url_for("auth.login"))
