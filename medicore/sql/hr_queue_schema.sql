CREATE TABLE IF NOT EXISTS staff_attendance (
    attendance_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    staff_id BIGINT NOT NULL,
    date DATE NOT NULL,
    clock_in_time TIME NULL,
    clock_out_time TIME NULL,
    status ENUM('Present', 'Absent', 'Half-Day', 'Leave') NOT NULL DEFAULT 'Present',
    INDEX idx_attendance_staff (staff_id),
    INDEX idx_attendance_date (date),
    CONSTRAINT fk_attendance_staff
        FOREIGN KEY (staff_id) REFERENCES users(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS staff_leave_requests (
    request_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    staff_id BIGINT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    leave_type VARCHAR(80) NOT NULL,
    status ENUM('Pending', 'Approved', 'Rejected') NOT NULL DEFAULT 'Pending',
    approved_by BIGINT NULL,
    INDEX idx_leave_staff (staff_id),
    INDEX idx_leave_status (status),
    CONSTRAINT fk_leave_staff
        FOREIGN KEY (staff_id) REFERENCES users(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_leave_approved_by
        FOREIGN KEY (approved_by) REFERENCES users(id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS payroll_records (
    payroll_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    staff_id BIGINT NOT NULL,
    month VARCHAR(12) NOT NULL,
    year INT NOT NULL,
    base_salary_lkr DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    bonuses_lkr DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    deductions_lkr DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    net_pay_lkr DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    payment_status ENUM('Pending', 'Paid') NOT NULL DEFAULT 'Pending',
    INDEX idx_payroll_staff (staff_id),
    INDEX idx_payroll_month (month, year),
    CONSTRAINT fk_payroll_staff
        FOREIGN KEY (staff_id) REFERENCES users(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS physical_queues (
    queue_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id VARCHAR(36) NOT NULL,
    doctor_id BIGINT NOT NULL,
    date DATE NOT NULL,
    queue_number INT NOT NULL,
    status ENUM('Waiting', 'In Consultation', 'Completed') NOT NULL DEFAULT 'Waiting',
    INDEX idx_queue_doctor_date (doctor_id, date),
    CONSTRAINT fk_queue_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_queue_doctor
        FOREIGN KEY (doctor_id) REFERENCES users(id)
        ON DELETE CASCADE ON UPDATE CASCADE
);
