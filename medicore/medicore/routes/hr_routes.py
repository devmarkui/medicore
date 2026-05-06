from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token

hr_bp = Blueprint("hr", __name__, url_prefix="/hr")

ALLOWED_ROLES = ["SuperAdmin", "CenterAdmin"]
DEFAULT_WORK_DAYS = 22


def _today_colombo() -> date:
    return datetime.now(ZoneInfo("Asia/Colombo")).date()


def _parse_decimal(value: str | None, default: str = "0.00") -> Decimal:
    try:
        return Decimal(value or default)
    except Exception:
        return Decimal(default)


def _load_staff():
    query = """
    SELECT user_id AS id, COALESCE(full_name, username) AS staff_name
    FROM users
    WHERE is_active = 1
        ORDER BY staff_name
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _load_attendance(selected_date: date):
    query = """
     SELECT a.attendance_id, a.staff_id, a.attendance_date, a.clock_in_time, a.clock_out_time, a.status,
               COALESCE(u.full_name, u.email) AS staff_name
        FROM staff_attendance a
     INNER JOIN users u ON u.user_id = a.staff_id
     WHERE a.attendance_date = %s
        ORDER BY u.full_name
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (selected_date,))
        return cursor.fetchall() or []


def _load_leave_requests():
    query = """
     SELECT r.leave_request_id, r.staff_id, r.start_date, r.end_date, r.leave_type, r.status,
               COALESCE(u.full_name, u.email) AS staff_name
    FROM staff_leave_requests r
    INNER JOIN users u ON u.user_id = r.staff_id
        ORDER BY r.start_date DESC
        LIMIT 100
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        return cursor.fetchall() or []


def _calculate_attendance_factor(staff_id: int, month: int, year: int) -> Decimal:
    query = """
        SELECT status, COUNT(*) AS total
    FROM staff_attendance
    WHERE staff_id = %s AND MONTH(attendance_date) = %s AND YEAR(attendance_date) = %s
        GROUP BY status
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (staff_id, month, year))
        rows = cursor.fetchall() or []

    present_days = Decimal("0")
    for row in rows:
        status = row["status"]
        total = Decimal(str(row["total"]))
        if status == "Present":
            present_days += total
        elif status == "Half-Day":
            present_days += total * Decimal("0.5")

    if present_days == 0:
        return Decimal("0")

    return (present_days / Decimal(DEFAULT_WORK_DAYS)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


@hr_bp.get("")
@login_required
@role_required(ALLOWED_ROLES)
def hr_dashboard():
    selected_date = request.args.get("date")
    if selected_date:
        selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
    else:
        selected_date = _today_colombo()

    staff = _load_staff()
    attendance = _load_attendance(selected_date)
    leave_requests = _load_leave_requests()

    return render_template(
        "hr/hr_dashboard.html",
        title="HR Dashboard",
        active_page="hr",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        staff=staff,
        attendance=attendance,
        leave_requests=leave_requests,
        selected_date=selected_date.isoformat(),
        csrf_token=generate_csrf_token(),
    )


@hr_bp.post("/leave/<int:request_id>/<action>")
@login_required
@role_required(ALLOWED_ROLES)
def handle_leave_request(request_id: int, action: str):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("hr.hr_dashboard"))

    status = "Approved" if action == "approve" else "Rejected"

    query = """
        UPDATE staff_leave_requests
        SET status = %s, approved_by = %s
    WHERE leave_request_id = %s
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (status, session.get("user_id"), request_id))

    flash(f"Leave request {status.lower()}.", "success")
    return redirect(url_for("hr.hr_dashboard"))


@hr_bp.post("/payroll/run")
@login_required
@role_required(ALLOWED_ROLES)
def run_payroll():
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("hr.hr_dashboard"))

    month = int(request.form.get("month") or _today_colombo().month)
    year = int(request.form.get("year") or _today_colombo().year)

    staff = _load_staff()
    insert_query = """
        INSERT INTO payroll_records (
            staff_id, payroll_month, payroll_year, base_salary_lkr, bonuses_lkr,
            deductions_lkr, net_pay_lkr, payment_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pending')
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        for member in staff:
            staff_id = member["id"]
            base_salary = _parse_decimal(request.form.get(f"base_salary_{staff_id}"))
            bonuses = _parse_decimal(request.form.get(f"bonuses_{staff_id}"))
            deductions = _parse_decimal(request.form.get(f"deductions_{staff_id}"))
            factor = _calculate_attendance_factor(staff_id, month, year)
            prorated_salary = (base_salary * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            net_pay = (prorated_salary + bonuses - deductions).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            cursor.execute(
                insert_query,
                (
                    staff_id,
                    month,
                    year,
                    prorated_salary,
                    bonuses,
                    deductions,
                    net_pay,
                ),
            )

    flash("Payroll generated for the selected month.", "success")
    return redirect(url_for("hr.hr_dashboard"))
