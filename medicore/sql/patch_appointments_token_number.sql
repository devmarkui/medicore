USE medicore;

ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS token_number INT NULL AFTER status;

CREATE INDEX IF NOT EXISTS idx_appointments_doctor_date_token
    ON appointments (doctor_id, appointment_date, token_number);
