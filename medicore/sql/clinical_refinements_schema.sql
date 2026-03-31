CREATE TABLE IF NOT EXISTS departments (
    department_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    department_name VARCHAR(120) NOT NULL,
    description TEXT NULL,
    status ENUM('Active', 'Inactive') NOT NULL DEFAULT 'Active',
    UNIQUE KEY uq_departments_name (department_name)
);

ALTER TABLE users
    ADD COLUMN department_id BIGINT NULL,
    ADD COLUMN two_factor_secret VARCHAR(80) NULL,
    ADD COLUMN is_2fa_enabled BOOLEAN NOT NULL DEFAULT 0,
    ADD CONSTRAINT fk_users_department
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
        ON DELETE SET NULL ON UPDATE CASCADE;

CREATE TABLE IF NOT EXISTS tax_rules (
    tax_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tax_name VARCHAR(120) NOT NULL,
    percentage DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    UNIQUE KEY uq_tax_rules_name (tax_name)
);

CREATE TABLE IF NOT EXISTS referral_letters (
    referral_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id VARCHAR(20) NOT NULL,
    referring_doctor_id BIGINT NOT NULL,
    referred_to_specialty VARCHAR(120) NOT NULL,
    clinical_justification TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_referrals_patient (patient_id),
    CONSTRAINT fk_referral_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_referral_doctor
        FOREIGN KEY (referring_doctor_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS patient_insurance (
    insurance_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id VARCHAR(20) NOT NULL,
    provider_name VARCHAR(120) NOT NULL,
    policy_number VARCHAR(120) NOT NULL,
    expiry_date DATE NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_insurance_patient (patient_id),
    CONSTRAINT fk_insurance_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);
