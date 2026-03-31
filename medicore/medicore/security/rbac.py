from functools import wraps
from http import HTTPStatus

from flask import abort, redirect, request, session, url_for

from medicore.security.audit import log_audit_action


ROLE_SUPERADMIN = "SUPERADMIN"
ROLE_STAFF = "STAFF"

ROLE_PERMISSIONS = {
    ROLE_SUPERADMIN: {
        "dashboard:view",
        "patients:manage",
        "appointments:manage",
        "clinical:manage",
        "pharmacy:manage",
        "lab:manage",
        "settings:manage",
    },
    ROLE_STAFF: {
        "dashboard:view",
        # Placeholder: more granular permission matrix to be added in later modules
    },
}


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("auth.login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


def role_required(allowed_roles: list[str]):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not session.get("authenticated"):
                return redirect(url_for("auth.login", next=request.path))

            user_role = session.get("role") or ""
            allowed_lower = {role.lower() for role in allowed_roles}
            user_role_lower = user_role.lower()
            if user_role_lower in {"superadmin", "super_admin"}:
                return view_func(*args, **kwargs)
            if user_role_lower not in allowed_lower:
                log_audit_action(
                    action_type="UNAUTHORIZED_ACCESS_ATTEMPT",
                    table_affected="rbac",
                    record_id=request.path,
                    old_values={"role": user_role},
                    new_values={"allowed_roles": allowed_roles},
                    async_log=True,
                )
                abort(HTTPStatus.FORBIDDEN)

            return view_func(*args, **kwargs)

        return wrapped

    return decorator
