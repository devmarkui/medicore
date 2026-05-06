from __future__ import annotations

import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, flash, redirect, render_template, request, session, url_for, current_app
from werkzeug.utils import secure_filename

from medicore.db.connection import get_db_cursor
from medicore.security.rbac import login_required, role_required
from medicore.security.web import generate_csrf_token, validate_csrf_token
from medicore.communications.communications_service import send_whatsapp_template
from medicore.inventory.inventory_service import reduce_stock_for_service

lab_bp = Blueprint("lab", __name__, url_prefix="/lab")

ALLOWED_ROLES = ["LabTechnician", "Admin", "SuperAdmin", "Doctor"]
ALLOWED_UPLOAD_EXTENSIONS = {".pdf"}


def _now_colombo() -> datetime:
    return datetime.now(ZoneInfo("Asia/Colombo"))


def _safe_upload_dir() -> str:
    directory = current_app.config.get("LAB_UPLOAD_DIR")
    if not directory:
        directory = os.path.join(current_app.instance_path, "lab_uploads")
    os.makedirs(directory, exist_ok=True)
    return directory


def _is_allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_UPLOAD_EXTENSIONS


def _save_pdf(file_storage) -> str | None:
    if not file_storage or file_storage.filename == "":
        return None

    filename = secure_filename(file_storage.filename)
    if not filename or not _is_allowed_file(filename):
        return None

    extension = os.path.splitext(filename)[1].lower()
    safe_name = f"{uuid.uuid4().hex}{extension}"
    upload_dir = _safe_upload_dir()
    file_path = os.path.join(upload_dir, safe_name)
    file_storage.save(file_path)
    return file_path


def _results_exist(order_id: str) -> bool:
    query = """
        SELECT COUNT(*) AS total
        FROM lab_results
        WHERE order_id = %s
          AND (result_value IS NOT NULL OR report_file_path IS NOT NULL)
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query, (order_id,))
        result = cursor.fetchone() or {}
    return int(result.get("total", 0)) > 0


@lab_bp.get("/dashboard")
@login_required
@role_required(ALLOWED_ROLES)
def lab_dashboard():
    query = """
        SELECT o.order_id, o.order_date, o.status,
               CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
               COALESCE(u.full_name, u.email) AS doctor_name
        FROM lab_orders o
        INNER JOIN patients p ON p.patient_id = o.patient_id
    INNER JOIN users u ON u.user_id = o.requesting_doctor_id
        ORDER BY o.order_date DESC
        LIMIT 200
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(query)
        orders = cursor.fetchall() or []

    return render_template(
        "lab/lab_dashboard.html",
        title="Lab Dashboard",
        active_page="lab",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        orders=orders,
        csrf_token=generate_csrf_token(),
    )


@lab_bp.post("/update-status/<order_id>")
@login_required
@role_required(ALLOWED_ROLES)
def update_status(order_id: str):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("lab.lab_dashboard"))

    new_status = request.form.get("status")
    if new_status == "Completed" and not _results_exist(order_id):
        flash("Add at least one result before completing the order.", "error")
        return redirect(url_for("lab.lab_order", order_id=order_id))

    update_query = """
        UPDATE lab_orders
        SET status = %s
        WHERE order_id = %s
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(update_query, (new_status, order_id))
        
        # --- Inventory Integration ---
        # 1. Deduct items mapped to 'Sample Collected'
        if new_status == "Sample Collected" or new_status == "Completed":
            cursor.execute("SELECT test_id FROM lab_results WHERE order_id = %s", (order_id,))
            results = cursor.fetchall() or []
            for r in results:
                # Deduct consumables used during sampling
                reduce_stock_for_service(
                    service_item_id=r['test_id'], 
                    service_qty=1, 
                    ref_type='Lab', 
                    ref_id=order_id, 
                    stage='on_sample_collection',
                    user_id=session.get("user_id")
                )

        # 2. Deduct items mapped to 'Completed' (e.g. reagents)
        if new_status == "Completed":
            cursor.execute("SELECT test_id FROM lab_results WHERE order_id = %s", (order_id,))
            results = cursor.fetchall() or []
            for r in results:
                # Deduct lab items used during test processing
                reduce_stock_for_service(
                    service_item_id=r['test_id'], 
                    service_qty=1, 
                    ref_type='Lab', 
                    ref_id=order_id, 
                    stage='on_completion',
                    user_id=session.get("user_id")
                )

    flash("Lab order status updated.", "success")
    return redirect(url_for("lab.lab_dashboard"))


@lab_bp.get("/order/<order_id>")
@login_required
@role_required(ALLOWED_ROLES)
def lab_order(order_id: str):
    order_query = """
        SELECT o.order_id, o.status, o.order_date, o.patient_id,
               CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
               p.nic_number, p.phone_number,
               COALESCE(u.full_name, u.email) AS doctor_name
        FROM lab_orders o
        INNER JOIN patients p ON p.patient_id = o.patient_id
    INNER JOIN users u ON u.user_id = o.requesting_doctor_id
        WHERE o.order_id = %s
        LIMIT 1
    """
    results_query = """
        SELECT r.result_id, r.test_id, r.result_value, r.is_abnormal, r.report_file_path,
               t.test_name, t.unit
        FROM lab_results r
        INNER JOIN lab_tests_master t ON t.test_id = r.test_id
        WHERE r.order_id = %s
        ORDER BY r.result_id ASC
    """
    tests_query = """
        SELECT test_id, test_name, unit
        FROM lab_tests_master
        ORDER BY test_name ASC
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(order_query, (order_id,))
        order = cursor.fetchone()
        if not order:
            flash("Lab order not found.", "error")
            return redirect(url_for("lab.lab_dashboard"))
        cursor.execute(results_query, (order_id,))
        results = cursor.fetchall() or []
        cursor.execute(tests_query)
        tests = cursor.fetchall() or []

    return render_template(
        "lab/lab_result_entry.html",
        title=f"Lab Order {order_id}",
        active_page="lab",
        current_user={
            "username": session.get("username", "User"),
            "role": session.get("role", ""),
        },
        order=order,
        results=results,
        tests=tests,
        csrf_token=generate_csrf_token(),
    )


@lab_bp.post("/upload-result/<order_id>")
@login_required
@role_required(ALLOWED_ROLES)
def upload_result(order_id: str):
    if not validate_csrf_token():
        flash("Invalid request token.", "error")
        return redirect(url_for("lab.lab_order", order_id=order_id))

    test_id = request.form.get("test_id")
    result_value = (request.form.get("result_value") or "").strip()
    is_abnormal = 1 if request.form.get("is_abnormal") == "on" else 0
    report_file = request.files.get("report_file")

    file_path = _save_pdf(report_file)
    if report_file and not file_path:
        flash("Only PDF reports are allowed.", "error")
        return redirect(url_for("lab.lab_order", order_id=order_id))

    if not test_id and not file_path and not result_value:
        flash("Provide a result value or upload a report file.", "error")
        return redirect(url_for("lab.lab_order", order_id=order_id))

    insert_query = """
        INSERT INTO lab_results (order_id, test_id, result_value, is_abnormal, report_file_path, entered_by)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    patient_query = """
        SELECT p.phone_number
        FROM lab_orders o
        INNER JOIN patients p ON p.patient_id = o.patient_id
        WHERE o.order_id = %s
        LIMIT 1
    """

    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(
            insert_query,
            (
                order_id,
                test_id,
                result_value or None,
                is_abnormal,
                file_path,
                session.get("user_id"),
            ),
        )

        cursor.execute(patient_query, (order_id,))
        patient = cursor.fetchone() or {}

    if patient.get("phone_number"):
        send_whatsapp_template(
            patient["phone_number"],
            template_name="lab_result_ready",
            variables=[order_id],
            patient_id=None,
            message_type="Lab Result",
        )

    flash("Lab result saved.", "success")
    return redirect(url_for("lab.lab_order", order_id=order_id))
