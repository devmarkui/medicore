from flask import Flask, redirect, url_for

from medicore.config import Config
from medicore.routes.auth_routes import auth_bp
from medicore.routes.dashboard_routes import dashboard_bp
from medicore.routes.appointment_routes import appointments_bp
from medicore.routes.billing_routes import billing_bp
from medicore.routes.clinical_routes import clinical_bp
from medicore.routes.pharmacy_routes import pharmacy_bp
from medicore.routes.lab_routes import lab_bp
from medicore.routes.communications_routes import communications_bp
from medicore.routes.settings_routes import settings_bp
from medicore.routes.analytics_routes import analytics_bp
from medicore.routes.hr_routes import hr_bp
from medicore.routes.queue_routes import queue_bp
from medicore.routes.staff_routes import staff_bp
from medicore.routes.patient_routes import patients_bp, patient_profile_bp
from medicore.routes.patient_portal_routes import portal_bp
from medicore.routes.telehealth_routes import telehealth_bp
from medicore.routes.clinical_refinements_routes import clinical_refinements_bp
from medicore.routes.reception_routes import reception_bp
from medicore.realtime.socketio import init_socketio
from medicore.i18n import init_i18n
from medicore.security.session_security import configure_session


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    configure_session(app)
    init_i18n(app)
    init_socketio(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(clinical_bp)
    app.register_blueprint(pharmacy_bp)
    app.register_blueprint(lab_bp)
    app.register_blueprint(communications_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(queue_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(patient_profile_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(telehealth_bp)
    app.register_blueprint(clinical_refinements_bp)
    app.register_blueprint(reception_bp)

    @app.get("/")
    def root_redirect():
        return redirect(url_for("dashboard.dashboard"))

    return app
