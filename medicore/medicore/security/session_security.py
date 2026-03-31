from datetime import datetime, timezone

from flask import Flask, session


def configure_session(app: Flask) -> None:
    """Harden session cookie behavior with secure defaults."""
    app.config["SESSION_COOKIE_HTTPONLY"] = app.config.get("SESSION_COOKIE_HTTPONLY", True)
    app.config["SESSION_COOKIE_SECURE"] = app.config.get("SESSION_COOKIE_SECURE", True)
    app.config["SESSION_COOKIE_SAMESITE"] = app.config.get("SESSION_COOKIE_SAMESITE", "Lax")


def rotate_session(user_id: int, username: str, role_name: str) -> None:
    """Prevent session fixation by clearing old session and setting fresh auth context."""
    session.clear()
    session.permanent = True
    session["authenticated"] = True
    session["user_id"] = int(user_id)
    session["username"] = username
    session["role"] = role_name
    session["login_at"] = datetime.now(timezone.utc).isoformat()


def destroy_session() -> None:
    session.clear()
