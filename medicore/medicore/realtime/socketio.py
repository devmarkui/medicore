from __future__ import annotations

from flask import session
from flask_socketio import SocketIO, emit, disconnect

socketio = SocketIO(async_mode="threading", cors_allowed_origins="*")


def init_socketio(app):
    socketio.init_app(app)


@socketio.on("connect", namespace="/internal_staff_chat")
def handle_connect():
    if not session.get("authenticated"):
        disconnect()
        return False
    emit("status", {"message": "Connected"})


@socketio.on("urgent_message", namespace="/internal_staff_chat")
def handle_urgent_message(data):
    if not session.get("authenticated"):
        disconnect()
        return
    message = (data or {}).get("message", "")
    sender = session.get("username", "Staff")
    emit(
        "urgent_message",
        {"message": message, "sender": sender},
        broadcast=True,
    )
