CREATE TABLE IF NOT EXISTS drugs_master (
    drug_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    generic_name VARCHAR(120) NOT NULL,
    brand_name VARCHAR(120) NOT NULL,
    form ENUM('Tablet', 'Capsule', 'Syrup', 'Injection', 'Ointment') NOT NULL,
    strength VARCHAR(40) NOT NULL,
    INDEX idx_drugs_generic (generic_name),
    INDEX idx_drugs_brand (brand_name)
);

CREATE TABLE IF NOT EXISTS prescriptions (
    prescription_id VARCHAR(20) PRIMARY KEY,
    consultation_id BIGINT NOT NULL,
    patient_id VARCHAR(36) NOT NULL,
    doctor_id BIGINT NOT NULL,
    prescription_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    general_instructions TEXT NULL,
    INDEX idx_prescriptions_patient (patient_id),
    INDEX idx_prescriptions_doctor (doctor_id),
    CONSTRAINT fk_prescriptions_consultation
        FOREIGN KEY (consultation_id) REFERENCES consultations(consultation_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_prescriptions_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_prescriptions_doctor
        FOREIGN KEY (doctor_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS prescription_items (
    item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    prescription_id VARCHAR(20) NOT NULL,
    drug_id BIGINT NOT NULL,
    dosage VARCHAR(60) NOT NULL,
    frequency VARCHAR(60) NOT NULL,
    duration_days INT NOT NULL,
    special_instructions VARCHAR(255) NULL,
    INDEX idx_prescription_items_rx (prescription_id),
    CONSTRAINT fk_prescription_items_rx
        FOREIGN KEY (prescription_id) REFERENCES prescriptions(prescription_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_prescription_items_drug
        FOREIGN KEY (drug_id) REFERENCES drugs_master(drug_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
);
