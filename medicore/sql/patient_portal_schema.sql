ALTER TABLE patients
    ADD COLUMN password_hash VARCHAR(255) NULL,
    ADD COLUMN portal_active BOOLEAN NOT NULL DEFAULT 0,
    ADD COLUMN portal_last_login TIMESTAMP NULL;

CREATE INDEX idx_patients_email ON patients (email);
