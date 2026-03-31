CREATE TABLE IF NOT EXISTS communication_templates (
    template_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    template_name VARCHAR(120) NOT NULL,
    channel ENUM('SMS', 'WhatsApp', 'Email') NOT NULL,
    content TEXT NOT NULL,
    variables_json TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_comm_templates_name (template_name)
);

CREATE TABLE IF NOT EXISTS communication_logs (
    log_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id VARCHAR(36) NULL,
    recipient_number VARCHAR(30) NOT NULL,
    channel ENUM('SMS', 'WhatsApp', 'Email') NOT NULL,
    direction ENUM('Outbound', 'Inbound') NOT NULL DEFAULT 'Outbound',
    message_type ENUM('Appointment Reminder', 'Lab Result', 'Billing', 'Marketing', 'Manual') NOT NULL,
    content TEXT NOT NULL,
    status ENUM('Queued', 'Sent', 'Delivered', 'Failed') NOT NULL DEFAULT 'Queued',
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_comm_logs_patient (patient_id),
    INDEX idx_comm_logs_status (status),
    CONSTRAINT fk_comm_logs_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);
