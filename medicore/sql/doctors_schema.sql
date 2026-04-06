CREATE TABLE IF NOT EXISTS doctors (
    doctor_id BIGINT UNSIGNED PRIMARY KEY,
    doctor_name VARCHAR(200) NOT NULL,
    doctor_code VARCHAR(64) NOT NULL UNIQUE,
    specialization VARCHAR(120),
    doctor_fee DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    hospital_fee DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_doctors_active_name (is_active, doctor_name),
    CONSTRAINT fk_doctors_user FOREIGN KEY (doctor_id)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
);
