# MediCore - Modular Clinic Management System

This workspace contains:
- Secure Flask web entrypoint and auth/session routes
- Role-based decorators for route protection
- Tailwind-based master UI layout and dashboard views
- Patient directory + registration + patient profile (EHR foundation)
- Patient self-service portal (login, booking, records, messaging)
- Clinical workspace, pharmacy, lab, billing, analytics, HR, and communications modules

## Quick structure
- `app.py`: Flask app factory and route registration
- `medicore/config.py`: app configuration from env
- `medicore/db/connection.py`: MariaDB connection factory
- `medicore/security/`: hashing, session helpers, CSRF/XSS helpers, decorators
- `medicore/routes/`: modular blueprints for each feature area
- `medicore/templates/`: Tailwind-powered UI templates
- `sql/`: MariaDB schemas (patients, appointments, clinical, billing, lab, pharmacy, etc.)

## Setup
1. Copy `.env.example` to `.env` and edit values.
2. Install deps with `pip install -r requirements.txt`.
3. Apply SQL schemas under `sql/` to your MariaDB instance.
4. Run the app with `python app.py`.

## Notes
- Uses prepared statements via `mysql-connector-python` (`cursor(prepared=True)`).
- Session cookies are configured to be `Secure`, `HttpOnly`, and `SameSite`.
- Template auto-escaping is enabled via Flask/Jinja by default.

## Reception / Channeling Desk (Single-Page Flow)

The receptionist workflow is now unified under one screen:

- Route: `/appointments/channeling-desk`
- Sections: Patient lookup/registration, doctor booking/token preview, billing/payment
- Business rule enforced: token is generated **only after successful payment**

### What it does in one submit

1. Uses selected existing patient or creates a new patient (phone duplicates allowed)
2. Creates appointment + invoice + payment records
3. Confirms payment first
4. Generates doctor-specific daily token after payment
5. Adds patient to doctor queue and shows booking summary

### Required DB patch

Apply this migration once on existing DBs:

- `sql/patch_appointments_token_number.sql`
- `sql/patch_doctors_management.sql`

This adds `appointments.token_number` and index `idx_appointments_doctor_date_token` used by paid-token sequencing.
It also creates the `doctors` table used by Settings → Doctor Management and dynamic doctor loading in channeling.
