CREATE DATABASE IF NOT EXISTS medicore CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE medicore;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS physical_queues;
DROP TABLE IF EXISTS payroll_records;
DROP TABLE IF EXISTS staff_leave_requests;
DROP TABLE IF EXISTS staff_attendance;
DROP TABLE IF EXISTS communication_logs;
DROP TABLE IF EXISTS lab_results;
DROP TABLE IF EXISTS pharmacy_sale_items;
DROP TABLE IF EXISTS pharmacy_sales;
DROP TABLE IF EXISTS referral_letters;
DROP TABLE IF EXISTS consultations;
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS patient_insurance;
DROP TABLE IF EXISTS lab_orders;
DROP TABLE IF EXISTS lab_tests_master;
DROP TABLE IF EXISTS inventory_batches;
DROP TABLE IF EXISTS prescription_items;
DROP TABLE IF EXISTS prescriptions;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS invoice_items;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS patient_vitals;
DROP TABLE IF EXISTS medical_history;
DROP TABLE IF EXISTS appointments;
DROP TABLE IF EXISTS doctors;
DROP TABLE IF EXISTS drugs_master;
DROP TABLE IF EXISTS patients;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS departments;
DROP TABLE IF EXISTS communication_templates;
DROP TABLE IF EXISTS tax_rules;
DROP TABLE IF EXISTS system_settings;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE system_settings (
    setting_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(120) NOT NULL UNIQUE,
    setting_value TEXT NOT NULL,
    description VARCHAR(255),
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tax_rules (
    tax_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tax_name VARCHAR(120) NOT NULL UNIQUE,
    percentage DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE communication_templates (
    template_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    template_name VARCHAR(120) NOT NULL UNIQUE,
    channel ENUM('SMS','WhatsApp','Email') NOT NULL,
    content TEXT NOT NULL,
    variables_json JSON NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE departments (
    department_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    department_name VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    status ENUM('Active','Inactive') NOT NULL DEFAULT 'Active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE users (
    user_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    department_id BIGINT UNSIGNED NULL,
    email VARCHAR(190) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
        full_name VARCHAR(200) NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(25),
    role ENUM('SuperAdmin','CenterAdmin','Doctor','Nurse','Receptionist','Pharmacist','LabTechnician') NOT NULL DEFAULT 'Receptionist',
    status ENUM('Active','Inactive') NOT NULL DEFAULT 'Active',
    two_factor_secret VARCHAR(64),
    is_2fa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL DEFAULT NULL,
    CONSTRAINT fk_users_department FOREIGN KEY (department_id)
        REFERENCES departments(department_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE doctors (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE patients (
    patient_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_number VARCHAR(20) NOT NULL UNIQUE,
    nic_number VARCHAR(20) UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE NULL,
    birth_year SMALLINT,
    gender ENUM('Male','Female','Other') NOT NULL,
    phone_number VARCHAR(25) NOT NULL,
    email VARCHAR(190),
    blood_group VARCHAR(5),
    address VARCHAR(255),
    city VARCHAR(80),
    district VARCHAR(80),
    emergency_contact_name VARCHAR(120),
    emergency_contact_phone VARCHAR(25),
    emergency_contact_relation VARCHAR(80),
    portal_password_hash VARCHAR(255),
    portal_active BOOLEAN NOT NULL DEFAULT FALSE,
    portal_last_login TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_patients_phone (phone_number),
    INDEX idx_patients_email (email),
    INDEX idx_patients_name (last_name, first_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE drugs_master (
    drug_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    generic_name VARCHAR(120) NOT NULL,
    brand_name VARCHAR(120) NOT NULL,
    form ENUM('Tablet','Capsule','Syrup','Injection','Ointment') NOT NULL,
    strength VARCHAR(40) NOT NULL,
    UNIQUE KEY uq_drugs_names (generic_name, brand_name, strength)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE appointments (
    appointment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_id BIGINT UNSIGNED NOT NULL,
    doctor_id BIGINT UNSIGNED NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    appointment_mode ENUM('In-Person','Online') NOT NULL DEFAULT 'In-Person',
    telehealth_link VARCHAR(255),
    reason_for_visit VARCHAR(255) NOT NULL,
    status ENUM('Scheduled','Checked-In','Completed','Cancelled') NOT NULL DEFAULT 'Scheduled',
    token_number INT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_appointments_patient (patient_id),
    INDEX idx_appointments_doctor (doctor_id),
    INDEX idx_appointments_date (appointment_date),
    INDEX idx_appointments_doctor_date_token (doctor_id, appointment_date, token_number),
    CONSTRAINT fk_appointments_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_appointments_doctor FOREIGN KEY (doctor_id)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE medical_history (
    medical_history_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_id BIGINT UNSIGNED NOT NULL UNIQUE,
    allergies TEXT,
    chronic_conditions TEXT,
    past_surgeries TEXT,
    family_history TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_medical_history_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE patient_vitals (
    vitals_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_id BIGINT UNSIGNED NOT NULL,
    blood_pressure VARCHAR(20),
    heart_rate VARCHAR(20),
    temperature DECIMAL(5,2),
    weight_kg DECIMAL(6,2),
    height_cm DECIMAL(6,2),
    record_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recorded_by BIGINT UNSIGNED,
    INDEX idx_vitals_patient_date (patient_id, record_date),
    CONSTRAINT fk_vitals_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_vitals_user FOREIGN KEY (recorded_by)
        REFERENCES users(user_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE invoices (
    invoice_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    invoice_number VARCHAR(30) NOT NULL UNIQUE,
    patient_id BIGINT UNSIGNED NOT NULL,
    appointment_id BIGINT UNSIGNED,
    subtotal DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    tax_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    total_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    status ENUM('Pending','Partial','Paid','Cancelled') NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by BIGINT UNSIGNED NOT NULL,
    CONSTRAINT fk_invoices_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_invoices_appointment FOREIGN KEY (appointment_id)
        REFERENCES appointments(appointment_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_invoices_user FOREIGN KEY (created_by)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE invoice_items (
    item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    invoice_id BIGINT UNSIGNED NOT NULL,
    description VARCHAR(255) NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    unit_price DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    line_total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    CONSTRAINT fk_invoice_items_invoice FOREIGN KEY (invoice_id)
        REFERENCES invoices(invoice_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE payments (
    payment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    invoice_id BIGINT UNSIGNED NOT NULL,
    amount_paid DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    payment_method ENUM('Cash','Card','Bank Transfer') NOT NULL,
    transaction_reference VARCHAR(120),
    payment_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_payments_invoice FOREIGN KEY (invoice_id)
        REFERENCES invoices(invoice_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE prescriptions (
    prescription_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    prescription_code VARCHAR(30) NOT NULL UNIQUE,
    appointment_id BIGINT UNSIGNED,
    patient_id BIGINT UNSIGNED NOT NULL,
    doctor_id BIGINT UNSIGNED NOT NULL,
    prescription_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    general_instructions TEXT,
    CONSTRAINT fk_prescriptions_appointment FOREIGN KEY (appointment_id)
        REFERENCES appointments(appointment_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_prescriptions_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_prescriptions_doctor FOREIGN KEY (doctor_id)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE prescription_items (
    prescription_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    prescription_id BIGINT UNSIGNED NOT NULL,
    drug_id BIGINT UNSIGNED NOT NULL,
    dosage VARCHAR(60) NOT NULL,
    frequency VARCHAR(60) NOT NULL,
    duration_days INT NOT NULL,
    special_instructions VARCHAR(255),
    CONSTRAINT fk_prescription_items_prescription FOREIGN KEY (prescription_id)
        REFERENCES prescriptions(prescription_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_prescription_items_drug FOREIGN KEY (drug_id)
        REFERENCES drugs_master(drug_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE inventory_batches (
    batch_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    drug_id BIGINT UNSIGNED NOT NULL,
    batch_number VARCHAR(60) NOT NULL,
    manufacturing_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    quantity_in_stock INT NOT NULL DEFAULT 0,
    purchase_price_lkr DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    selling_price_lkr DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    supplier_details VARCHAR(255),
    UNIQUE KEY uq_inventory_batch (drug_id, batch_number),
    CONSTRAINT fk_inventory_batches_drug FOREIGN KEY (drug_id)
        REFERENCES drugs_master(drug_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE lab_tests_master (
    test_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    test_name VARCHAR(180) NOT NULL,
    category VARCHAR(120) NOT NULL,
    normal_range VARCHAR(120),
    unit VARCHAR(60),
    price_lkr DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    UNIQUE KEY uq_lab_tests_name (test_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE lab_orders (
    order_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_number VARCHAR(30) NOT NULL UNIQUE,
    patient_id BIGINT UNSIGNED NOT NULL,
    requesting_doctor_id BIGINT UNSIGNED NOT NULL,
    appointment_id BIGINT UNSIGNED,
    order_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('Pending','Sample Collected','Processing','Completed','Cancelled') NOT NULL DEFAULT 'Pending',
    notes TEXT,
    CONSTRAINT fk_lab_orders_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_lab_orders_doctor FOREIGN KEY (requesting_doctor_id)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_lab_orders_appointment FOREIGN KEY (appointment_id)
        REFERENCES appointments(appointment_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE patient_insurance (
    insurance_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_id BIGINT UNSIGNED NOT NULL,
    provider_name VARCHAR(120) NOT NULL,
    policy_number VARCHAR(120) NOT NULL UNIQUE,
    expiry_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_patient_insurance_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE audit_logs (
    audit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED,
    action_type VARCHAR(120) NOT NULL,
    table_affected VARCHAR(120) NOT NULL,
    record_id BIGINT UNSIGNED,
    old_values JSON,
    new_values JSON,
    ip_address VARCHAR(45),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_logs_user FOREIGN KEY (user_id)
        REFERENCES users(user_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE consultations (
    consultation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    appointment_id BIGINT UNSIGNED,
    patient_id BIGINT UNSIGNED NOT NULL,
    doctor_id BIGINT UNSIGNED,
    consultation_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    chief_complaint VARCHAR(255) NOT NULL,
    clinical_notes TEXT,
    diagnosis VARCHAR(255),
    CONSTRAINT fk_consultations_appointment FOREIGN KEY (appointment_id)
        REFERENCES appointments(appointment_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_consultations_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_consultations_doctor FOREIGN KEY (doctor_id)
        REFERENCES users(user_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE referral_letters (
    referral_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_id BIGINT UNSIGNED NOT NULL,
    referring_doctor_id BIGINT UNSIGNED NOT NULL,
    department_id BIGINT UNSIGNED,
    referred_to VARCHAR(180) NOT NULL,
    clinical_justification TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_referrals_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_referrals_doctor FOREIGN KEY (referring_doctor_id)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_referrals_department FOREIGN KEY (department_id)
        REFERENCES departments(department_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE pharmacy_sales (
    sale_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_id BIGINT UNSIGNED,
    prescription_id BIGINT UNSIGNED,
    total_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    payment_method ENUM('Cash','Card','Bank Transfer') NOT NULL,
    sale_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sold_by BIGINT UNSIGNED NOT NULL,
    CONSTRAINT fk_pharmacy_sales_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_pharmacy_sales_prescription FOREIGN KEY (prescription_id)
        REFERENCES prescriptions(prescription_id) ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_pharmacy_sales_staff FOREIGN KEY (sold_by)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE pharmacy_sale_items (
    sale_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    sale_id BIGINT UNSIGNED NOT NULL,
    batch_id BIGINT UNSIGNED NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    subtotal DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    CONSTRAINT fk_sale_items_sale FOREIGN KEY (sale_id)
        REFERENCES pharmacy_sales(sale_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_sale_items_batch FOREIGN KEY (batch_id)
        REFERENCES inventory_batches(batch_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE lab_results (
    result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT UNSIGNED NOT NULL,
    test_id BIGINT UNSIGNED NOT NULL,
    result_value VARCHAR(255),
    is_abnormal BOOLEAN NOT NULL DEFAULT FALSE,
    report_file_path VARCHAR(255),
    entered_by BIGINT UNSIGNED NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_lab_results_order FOREIGN KEY (order_id)
        REFERENCES lab_orders(order_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_lab_results_test FOREIGN KEY (test_id)
        REFERENCES lab_tests_master(test_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_lab_results_user FOREIGN KEY (entered_by)
        REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE communication_logs (
    log_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_id BIGINT UNSIGNED,
    recipient_number VARCHAR(30) NOT NULL,
    channel ENUM('SMS','WhatsApp','Email') NOT NULL,
    direction ENUM('Outbound','Inbound') NOT NULL DEFAULT 'Outbound',
    message_type ENUM('Appointment Reminder','Lab Result','Billing','Marketing','Manual') NOT NULL,
    content TEXT NOT NULL,
    status ENUM('Queued','Sent','Delivered','Failed') NOT NULL DEFAULT 'Queued',
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comm_logs_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE staff_attendance (
    attendance_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    staff_id BIGINT UNSIGNED NOT NULL,
    attendance_date DATE NOT NULL,
    clock_in_time TIME,
    clock_out_time TIME,
    status ENUM('Present','Absent','Half-Day','Leave') NOT NULL DEFAULT 'Present',
    CONSTRAINT fk_attendance_staff FOREIGN KEY (staff_id)
        REFERENCES users(user_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE staff_leave_requests (
    leave_request_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    staff_id BIGINT UNSIGNED NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    leave_type VARCHAR(80) NOT NULL,
    status ENUM('Pending','Approved','Rejected') NOT NULL DEFAULT 'Pending',
    approved_by BIGINT UNSIGNED,
    CONSTRAINT fk_leave_staff FOREIGN KEY (staff_id)
        REFERENCES users(user_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_leave_approver FOREIGN KEY (approved_by)
        REFERENCES users(user_id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE payroll_records (
    payroll_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    staff_id BIGINT UNSIGNED NOT NULL,
    payroll_month TINYINT NOT NULL,
    payroll_year SMALLINT NOT NULL,
    base_salary_lkr DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    bonuses_lkr DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    deductions_lkr DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    net_pay_lkr DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    payment_status ENUM('Pending','Paid') NOT NULL DEFAULT 'Pending',
    processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_payroll_staff FOREIGN KEY (staff_id)
        REFERENCES users(user_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE physical_queues (
    queue_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    patient_id BIGINT UNSIGNED NOT NULL,
    doctor_id BIGINT UNSIGNED NOT NULL,
    queue_date DATE NOT NULL,
    queue_number INT NOT NULL,
    status ENUM('Waiting','In Consultation','Completed') NOT NULL DEFAULT 'Waiting',
    CONSTRAINT fk_queue_patient FOREIGN KEY (patient_id)
        REFERENCES patients(patient_id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_queue_doctor FOREIGN KEY (doctor_id)
        REFERENCES users(user_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO departments (department_name, description, status)
VALUES ('General Practice', 'Primary care and family medicine', 'Active');

INSERT INTO tax_rules (tax_name, percentage, is_active)
VALUES 
    ('VAT', 15.00, TRUE),
    ('SSCL', 2.50, TRUE);

INSERT INTO users (
    department_id,
    email,
    password_hash,
         full_name,
    first_name,
    last_name,
    phone_number,
    role,
    status,
    two_factor_secret,
    is_2fa_enabled
) VALUES (
    (SELECT department_id FROM departments WHERE department_name = 'General Practice' LIMIT 1),
    'admin@medicore.local',
    '$argon2id$v=19$m=65536,t=3,p=4$KMLjJE2B6BwWBJiaYfwvjg$eUq9Ug7tjTDH3II87DgeIR16ssq02ZoEWrzHPsdHo/0',
         'System Admin',
    'System',
    'Admin',
    '+94112223333',
    'SuperAdmin',
    'Active',
    NULL,
    FALSE
);
