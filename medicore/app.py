from medicore import create_app
from medicore.realtime.socketio import socketio

app = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5001, debug=app.config.get("DEBUG", False))