from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import urllib.request

from flask import current_app

from medicore.db.connection import get_db_cursor

_executor = ThreadPoolExecutor(max_workers=4)


def normalize_phone(number: str) -> str:
    digits = re.sub(r"[^0-9]", "", number or "")
    if digits.startswith("94"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    if not digits:
        return ""
    return f"+94{digits}"


def _log_message(patient_id: str | None, recipient: str, channel: str, message_type: str, content: str, status: str) -> int:
    insert_query = """
        INSERT INTO communication_logs (
            patient_id, recipient_number, channel, direction, message_type, content, status, timestamp
        ) VALUES (%s, %s, %s, 'Outbound', %s, %s, %s, NOW())
    """
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(insert_query, (patient_id, recipient, channel, message_type, content, status))
        return cursor.lastrowid


def _update_log_status(log_id: int, status: str) -> None:
    update_query = "UPDATE communication_logs SET status = %s WHERE log_id = %s"
    with get_db_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute(update_query, (status, log_id))


def _post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def send_sms(number: str, message: str, patient_id: str | None = None, message_type: str = "Manual") -> None:
    normalized = normalize_phone(number)
    if not normalized:
        return

    log_id = _log_message(patient_id, normalized, "SMS", message_type, message, "Queued")

    def _task():
        try:
            api_url = current_app.config.get("SMS_API_URL")
            api_key = current_app.config.get("SMS_API_KEY")
            sender_id = current_app.config.get("SMS_SENDER_ID")
            if not api_url or not api_key:
                _update_log_status(log_id, "Failed")
                return
            payload = {
                "to": normalized,
                "message": message,
                "sender": sender_id,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            _post_json(api_url, payload, headers)
            _update_log_status(log_id, "Sent")
        except Exception:
            _update_log_status(log_id, "Failed")

    _executor.submit(_task)


def send_whatsapp_template(
    number: str,
    template_name: str,
    variables: list[str],
    patient_id: str | None = None,
    message_type: str = "Manual",
) -> None:
    normalized = normalize_phone(number)
    if not normalized:
        return

    content_preview = f"Template: {template_name} | Vars: {', '.join(variables)}"
    log_id = _log_message(patient_id, normalized, "WhatsApp", message_type, content_preview, "Queued")

    def _task():
        try:
            api_url = current_app.config.get("WHATSAPP_API_URL")
            api_token = current_app.config.get("WHATSAPP_API_TOKEN")
            phone_id = current_app.config.get("WHATSAPP_PHONE_ID")
            if not api_url or not api_token or not phone_id:
                _update_log_status(log_id, "Failed")
                return
            payload = {
                "messaging_product": "whatsapp",
                "to": normalized.replace("+", ""),
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": "en"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": value} for value in variables
                            ],
                        }
                    ],
                },
            }
            headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            }
            _post_json(f"{api_url}/{phone_id}/messages", payload, headers)
            _update_log_status(log_id, "Sent")
        except Exception:
            _update_log_status(log_id, "Failed")

    _executor.submit(_task)
