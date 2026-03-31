CREATE TABLE IF NOT EXISTS lab_tests_master (
    test_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    test_name VARCHAR(180) NOT NULL,
    category VARCHAR(120) NOT NULL,
    normal_range VARCHAR(120) NULL,
    unit VARCHAR(60) NULL,
    price_lkr DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    INDEX idx_lab_tests_name (test_name),
    INDEX idx_lab_tests_category (category)
);

CREATE TABLE IF NOT EXISTS lab_orders (
    order_id VARCHAR(20) PRIMARY KEY,
    patient_id VARCHAR(36) NOT NULL,
    prescribing_doctor_id BIGINT NOT NULL,
    consultation_id BIGINT NULL,
    order_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('Pending', 'Sample Collected', 'Processing', 'Completed', 'Cancelled') NOT NULL DEFAULT 'Pending',
    INDEX idx_lab_orders_patient (patient_id),
    INDEX idx_lab_orders_status (status),
    CONSTRAINT fk_lab_orders_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_lab_orders_doctor
        FOREIGN KEY (prescribing_doctor_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_lab_orders_consultation
        FOREIGN KEY (consultation_id) REFERENCES consultations(consultation_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS lab_results (
    result_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(20) NOT NULL,
    test_id BIGINT NOT NULL,
    result_value VARCHAR(255) NULL,
    is_abnormal BOOLEAN NOT NULL DEFAULT 0,
    report_file_path VARCHAR(255) NULL,
    entered_by BIGINT NOT NULL,
    INDEX idx_lab_results_order (order_id),
    CONSTRAINT fk_lab_results_order
        FOREIGN KEY (order_id) REFERENCES lab_orders(order_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_lab_results_test
        FOREIGN KEY (test_id) REFERENCES lab_tests_master(test_id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_lab_results_entered_by
        FOREIGN KEY (entered_by) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
);
