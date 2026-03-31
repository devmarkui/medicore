from contextlib import contextmanager
import re

import mysql.connector
from flask import current_app


class DatabaseConnectionError(Exception):
    """Raised when database connection cannot be established."""


def get_connection():
    """Create a new MariaDB connection using app configuration."""
    try:
        return mysql.connector.connect(
            host=current_app.config["DB_HOST"],
            port=current_app.config["DB_PORT"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
            database=current_app.config["DB_NAME"],
            autocommit=False,
        )
    except mysql.connector.Error as exc:
        raise DatabaseConnectionError("Failed to connect to database") from exc


@contextmanager
def get_db_cursor(dictionary: bool = True):
    """
    Context manager returning (connection, prepared cursor).

    All SQL execution should go through this helper to ensure prepared statements.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=dictionary, prepared=True)
    original_execute = cursor.execute

    def guarded_execute(query, params=None):
        if query:
            lowered = str(query).lower()
            if re.search(r"\bupdate\s+audit_logs\b", lowered) or re.search(r"\bdelete\s+from\s+audit_logs\b", lowered):
                raise ValueError("audit_logs is append-only and cannot be mutated")
        return original_execute(query, params)

    cursor.execute = guarded_execute
    try:
        yield conn, cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
