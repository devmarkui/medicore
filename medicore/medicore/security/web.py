import secrets

from flask import request, session
from markupsafe import escape


def generate_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf_token() -> bool:
    session_token = session.get("csrf_token")
    form_token = request.form.get("csrf_token", "")
    return bool(session_token) and secrets.compare_digest(session_token, form_token)


def sanitize_text(value: str) -> str:
    # Jinja escapes by default; this helper is for explicit sanitization in Python when needed.
    return str(escape(value))
