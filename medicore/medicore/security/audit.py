from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from flask import current_app, request, session

from medicore.db.connection import get_db_cursor

_executor = ThreadPoolExecutor(max_workers=2)


def _resolve_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def _insert_audit_log(
    user_id: int | None,
    action_type: str,
    table_affected: str,
    record_id: str | None,
    old_values: dict | None,
    new_values: dict | None,
    ip_address: str,
) -> None:
    insert_query = """
        INSERT INTO audit_logs (
            user_id, action_type, table_affected, record_id,
            old_values, new_values, ip_address, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            insert_query,
            (
                user_id,
                action_type,
                table_affected,
                record_id,
                json.dumps(old_values) if old_values is not None else None,
                json.dumps(new_values) if new_values is not None else None,
                ip_address,
            ),
        )


def log_audit_action(
    action_type: str,
    table_affected: str,
    record_id: str | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
    async_log: bool = True,
) -> None:
    user_id = session.get("user_id")
    ip_address = _resolve_ip()
    app = current_app._get_current_object()

    def _task():
        with app.app_context():
            _insert_audit_log(user_id, action_type, table_affected, record_id, old_values, new_values, ip_address)

    if async_log:
        _executor.submit(_task)
    else:
        _task()


def audit_log(action_type: str, table_affected: str, record_id_key: str | None = None):
    def decorator(view_func):
        def wrapper(*args, **kwargs):
            response = view_func(*args, **kwargs)
            record_id = None
            if record_id_key:
                record_id = request.view_args.get(record_id_key) if request.view_args else None
            payload: dict[str, Any] | None = None
            if request.is_json:
                payload = request.get_json(silent=True) or {}
            elif request.form:
                payload = request.form.to_dict()
            log_audit_action(action_type, table_affected, record_id=record_id, new_values=payload)
            return response

        wrapper.__name__ = view_func.__name__
        wrapper.__doc__ = view_func.__doc__
        return wrapper

    return decorator
