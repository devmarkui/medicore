from __future__ import annotations

import csv
from datetime import datetime, timedelta
from io import StringIO

from flask import Blueprint, Response, jsonify, render_template, request, session

from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")

ALLOWED_ROLES = ["SuperAdmin", "CenterAdmin"]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _default_range():
    end = datetime.utcnow().date()
    start = end - timedelta(days=6)
    return start, end


def _get_date_range():
    start = _parse_date(request.args.get("start_date"))
    end = _parse_date(request.args.get("end_date"))
    if not start or not end:
        return _default_range()
    return start.date(), end.date()


def _fetch_financial_summary(start_date, end_date):
    invoice_query = """
        SELECT
            COALESCE(SUM(total_amount), 0) AS invoice_revenue,
            COALESCE(SUM(discount_amount), 0) AS total_discounts,
            COALESCE(SUM(tax_amount), 0) AS total_tax
        FROM invoices
        WHERE status != 'Cancelled'
          AND DATE(created_at) BETWEEN %s AND %s
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(invoice_query, (start_date, end_date))
        invoice = cursor.fetchone() or {}

    return {
        "invoice_revenue": float(invoice.get("invoice_revenue", 0)),
        "total_discounts": float(invoice.get("total_discounts", 0)),
        "total_tax": float(invoice.get("total_tax", 0)),
    }


def _fetch_revenue_by_day(start_date, end_date):
    query = """
        SELECT DATE(created_at) AS day, SUM(total_amount) AS revenue
        FROM invoices
        WHERE status != 'Cancelled'
          AND DATE(created_at) BETWEEN %s AND %s
        GROUP BY day
        ORDER BY day ASC
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall() or []
    return rows


def _fetch_appointments_by_doctor(start_date, end_date):
    query = """
        SELECT COALESCE(u.full_name, u.email) AS doctor_name, COUNT(*) AS total
        FROM appointments a
        INNER JOIN users u ON u.user_id = a.doctor_id
        WHERE DATE(a.appointment_date) BETWEEN %s AND %s
        GROUP BY u.user_id
        ORDER BY total DESC
        LIMIT 10
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (start_date, end_date))
        return cursor.fetchall() or []


def _fetch_operational_metrics(start_date, end_date):
    cancellation_query = """
        SELECT
            COALESCE(SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END), 0) AS cancelled,
            COUNT(*) AS total
        FROM appointments
        WHERE DATE(appointment_date) BETWEEN %s AND %s
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(cancellation_query, (start_date, end_date))
        row = cursor.fetchone() or {}

    total = row.get("total", 0) or 0
    cancelled = row.get("cancelled", 0) or 0
    cancellation_rate = (cancelled / total) * 100 if total else 0

    return {
        "appointments_total": int(total),
        "appointments_cancelled": int(cancelled),
        "cancellation_rate": round(cancellation_rate, 2),
    }


def _fetch_clinical_metrics(start_date, end_date):
    top_drugs_query = """
        SELECT d.generic_name, d.brand_name, COUNT(*) AS total
        FROM prescription_items i
        INNER JOIN drugs_master d ON d.drug_id = i.drug_id
        INNER JOIN prescriptions p ON p.prescription_id = i.prescription_id
        WHERE DATE(p.prescription_date) BETWEEN %s AND %s
        GROUP BY d.drug_id
        ORDER BY total DESC
        LIMIT 5
    """

    diagnoses_query = """
        SELECT diagnosis, COUNT(*) AS total
        FROM consultations
        WHERE diagnosis IS NOT NULL
          AND diagnosis != ''
          AND DATE(consultation_date) BETWEEN %s AND %s
        GROUP BY diagnosis
        ORDER BY total DESC
        LIMIT 5
    """

    lab_query = """
        SELECT COUNT(*) AS total
        FROM lab_results r
        INNER JOIN lab_orders o ON o.order_id = r.order_id
        WHERE DATE(o.order_date) BETWEEN %s AND %s
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(top_drugs_query, (start_date, end_date))
        top_drugs = cursor.fetchall() or []
        cursor.execute(diagnoses_query, (start_date, end_date))
        top_diagnoses = cursor.fetchall() or []
        cursor.execute(lab_query, (start_date, end_date))
        lab_count = cursor.fetchone() or {}

    return {
        "top_drugs": top_drugs,
        "top_diagnoses": top_diagnoses,
        "lab_tests": int(lab_count.get("total", 0)),
    }


@analytics_bp.get("")
@login_required
@role_required(ALLOWED_ROLES)
def analytics_dashboard():
    start_date, end_date = _get_date_range()
    return render_template(
        "analytics/admin_analytics.html",
        title="Analytics",
        active_page="analytics",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        csrf_token=generate_csrf_token(),
    )


@analytics_bp.get("/data")
@login_required
@role_required(ALLOWED_ROLES)
def analytics_data():
    start_date, end_date = _get_date_range()

    summary = _fetch_financial_summary(start_date, end_date)
    revenue_by_day = _fetch_revenue_by_day(start_date, end_date)
    appointments_by_doctor = _fetch_appointments_by_doctor(start_date, end_date)
    operational = _fetch_operational_metrics(start_date, end_date)
    clinical = _fetch_clinical_metrics(start_date, end_date)

    return jsonify({
        "summary": summary,
        "revenue_by_day": revenue_by_day,
        "appointments_by_doctor": appointments_by_doctor,
        "operational": operational,
        "clinical": clinical,
    })


@analytics_bp.get("/export/financial")
@login_required
@role_required(ALLOWED_ROLES)
def export_financial_csv():
    start_date, end_date = _get_date_range()

    ledger_query = """
        SELECT DATE(created_at) AS entry_date, invoice_id AS ref_id,
               patient_id, total_amount, tax_amount, discount_amount, 'Invoice' AS source
        FROM invoices
        WHERE status != 'Cancelled'
          AND DATE(created_at) BETWEEN %s AND %s
        ORDER BY entry_date ASC
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(ledger_query, (start_date, end_date))
        rows = cursor.fetchall() or []

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "source", "reference", "patient_id", "total_amount", "tax_amount", "discount_amount"])
    for row in rows:
        writer.writerow([
            row.get("entry_date"),
            row.get("source"),
            row.get("ref_id"),
            row.get("patient_id"),
            row.get("total_amount"),
            row.get("tax_amount"),
            row.get("discount_amount"),
        ])

    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=financial_export.csv"
    return response
