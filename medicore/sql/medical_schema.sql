CREATE TABLE IF NOT EXISTS medical_history (
    patient_id VARCHAR(20) PRIMARY KEY,
    allergies TEXT,
    chronic_conditions TEXT,
    past_surgeries TEXT,
    family_history TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_medical_history_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS patient_vitals (
    vitals_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id VARCHAR(20) NOT NULL,
    blood_pressure VARCHAR(20),
    heart_rate VARCHAR(20),
    temperature DECIMAL(5,2),
    weight_kg DECIMAL(6,2),
    height_cm DECIMAL(6,2),
    record_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recorded_by BIGINT,
    INDEX idx_vitals_patient_date (patient_id, record_date),
    CONSTRAINT fk_vitals_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_vitals_user
        FOREIGN KEY (recorded_by) REFERENCES users(id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS consultations (
    consultation_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id VARCHAR(20) NOT NULL,
    doctor_id BIGINT,
    consultation_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    chief_complaint VARCHAR(255) NOT NULL,
    clinical_notes TEXT,
    diagnosis VARCHAR(255),
    INDEX idx_consultations_patient_date (patient_id, consultation_date),
    CONSTRAINT fk_consultations_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_consultations_doctor
        FOREIGN KEY (doctor_id) REFERENCES users(id)
        ON DELETE SET NULL ON UPDATE CASCADE
);
