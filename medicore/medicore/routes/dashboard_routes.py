from flask import Blueprint, render_template, session

from medicore.security.rbac import login_required
from medicore.security.web import generate_csrf_token

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/dashboard")
@login_required
def dashboard():
    stats = {
        "total_patients": "1,248",
        "appointments_today": "37",
        "pending_lab_results": "14",
        "today_revenue_lkr": "452,900",
    }

    return render_template(
        "dashboard.html",
        title="Dashboard",
        active_page="dashboard",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", "STAFF"),
        },
        stats=stats,
        csrf_token=generate_csrf_token(),
    )
