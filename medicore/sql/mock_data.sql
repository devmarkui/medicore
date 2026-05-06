USE medicore;
SET FOREIGN_KEY_CHECKS = 0;

-- ─── DEPARTMENTS ────────────────────────────────────────────────────────────
INSERT IGNORE INTO departments (department_name, description, status) VALUES
('General Practice',   'Primary care and family medicine',      'Active'),
('Cardiology',         'Heart and cardiovascular diseases',      'Active'),
('Neurology',          'Brain and nervous system disorders',     'Active'),
('Orthopedics',        'Bone, joint and muscle care',           'Active'),
('Laboratory',         'Diagnostic lab services',               'Active'),
('Pharmacy',           'Dispensing and medication management',  'Active'),
('Radiology',          'Imaging and scan services',             'Active');

-- ─── USERS (staff) ──────────────────────────────────────────────────────────
-- password hash = Admin@123 (argon2id)
INSERT IGNORE INTO users (department_id, email, password_hash, full_name, first_name, last_name, phone_number, role, status, is_2fa_enabled) VALUES
(2, 'dr.silva@medicore.local',   '$argon2id$v=19$m=65536,t=3,p=4$tsybwUssIrcLwchHx2/TYA$DC1x+KGOPwkmBBqzvDXFmRJVx8UWohm5KbKuUMz0PBM', 'Dr. Kamal Silva',      'Kamal',    'Silva',     '+94771234001', 'Doctor',        'Active', 0),
(3, 'dr.perera@medicore.local',  '$argon2id$v=19$m=65536,t=3,p=4$tsybwUssIrcLwchHx2/TYA$DC1x+KGOPwkmBBqzvDXFmRJVx8UWohm5KbKuUMz0PBM', 'Dr. Nimal Perera',     'Nimal',    'Perera',    '+94771234002', 'Doctor',        'Active', 0),
(4, 'dr.fernando@medicore.local','$argon2id$v=19$m=65536,t=3,p=4$tsybwUssIrcLwchHx2/TYA$DC1x+KGOPwkmBBqzvDXFmRJVx8UWohm5KbKuUMz0PBM', 'Dr. Amali Fernando',   'Amali',    'Fernando',  '+94771234003', 'Doctor',        'Active', 0),
(1, 'reception1@medicore.local', '$argon2id$v=19$m=65536,t=3,p=4$tsybwUssIrcLwchHx2/TYA$DC1x+KGOPwkmBBqzvDXFmRJVx8UWohm5KbKuUMz0PBM', 'Sanduni Rajapaksa',    'Sanduni',  'Rajapaksa', '+94771234004', 'Receptionist',  'Active', 0),
(5, 'lab1@medicore.local',       '$argon2id$v=19$m=65536,t=3,p=4$tsybwUssIrcLwchHx2/TYA$DC1x+KGOPwkmBBqzvDXFmRJVx8UWohm5KbKuUMz0PBM', 'Ruwan Bandara',        'Ruwan',    'Bandara',   '+94771234005', 'LabTechnician', 'Active', 0),
(6, 'pharma1@medicore.local',    '$argon2id$v=19$m=65536,t=3,p=4$tsybwUssIrcLwchHx2/TYA$DC1x+KGOPwkmBBqzvDXFmRJVx8UWohm5KbKuUMz0PBM', 'Nimali Wijesinghe',    'Nimali',   'Wijesinghe','+94771234006', 'Pharmacist',    'Active', 0),
(1, 'nurse1@medicore.local',     '$argon2id$v=19$m=65536,t=3,p=4$tsybwUssIrcLwchHx2/TYA$DC1x+KGOPwkmBBqzvDXFmRJVx8UWohm5KbKuUMz0PBM', 'Priya Kumari',         'Priya',    'Kumari',    '+94771234007', 'Nurse',         'Active', 0);

-- ─── DOCTORS ────────────────────────────────────────────────────────────────
INSERT IGNORE INTO doctors (doctor_id, doctor_name, doctor_code, specialization, doctor_fee, hospital_fee, is_active)
SELECT u.user_id, u.full_name,
  CONCAT('DR', LPAD(u.user_id,3,'0')),
  CASE u.email
    WHEN 'dr.silva@medicore.local'    THEN 'Cardiologist'
    WHEN 'dr.perera@medicore.local'   THEN 'Neurologist'
    WHEN 'dr.fernando@medicore.local' THEN 'Orthopedic Surgeon'
  END,
  CASE u.email
    WHEN 'dr.silva@medicore.local'    THEN 1500.00
    WHEN 'dr.perera@medicore.local'   THEN 1800.00
    WHEN 'dr.fernando@medicore.local' THEN 2000.00
  END,
  500.00, 1
FROM users u WHERE u.role = 'Doctor';

-- ─── PATIENTS ───────────────────────────────────────────────────────────────
INSERT IGNORE INTO patients (patient_number, nic_number, first_name, last_name, date_of_birth, gender, phone_number, email, blood_group, address, city) VALUES
('PAT-1001','199012345678','Ashan',    'Wickrama',  '1990-03-15','Male',  '0771234101','ashan@gmail.com',   'A+','12 Main St',     'Colombo'),
('PAT-1002','198556789012','Dilini',   'Rathnayake','1985-07-22','Female','0771234102','dilini@gmail.com',  'B+','45 Lake Road',    'Kandy'),
('PAT-1003','200198765432','Tharindu', 'Gunawardena','2001-11-08','Male', '0771234103','tharindu@gmail.com','O+','78 Hill Street',  'Galle'),
('PAT-1004','197834561234','Kumari',   'Dissanayake','1978-05-30','Female','0771234104','kumari@gmail.com', 'AB+','90 Temple Rd',   'Matara'),
('PAT-1005','199267890123','Nuwan',    'Jayasekara','1992-09-12','Male',  '0771234105','nuwan@gmail.com',   'A-','23 Beach Rd',    'Negombo'),
('PAT-1006','198845670123','Hasini',   'Bandara',   '1988-02-17','Female','0771234106','hasini@gmail.com',  'O-','56 Park Ave',    'Kurunegala'),
('PAT-1007','200367891234','Ishan',    'Madushanka','2003-04-25','Male',  '0771234107','ishan@gmail.com',   'B-','34 Queen St',    'Jaffna'),
('PAT-1008','197523456789','Nirosha',  'Senaratne', '1975-12-03','Female','0771234108','nirosha@gmail.com', 'A+','67 Church Rd',   'Anuradhapura'),
('PAT-1009','199134567890','Lasith',   'Malinga',   '1991-06-18','Male',  '0771234109','lasith@gmail.com',  'AB-','89 New Rd',    'Colombo'),
('PAT-1010','198623456780','Sachini',  'Perera',    '1986-08-09','Female','0771234110','sachini@gmail.com', 'B+','12 Sea View',    'Gampaha');

-- ─── APPOINTMENTS ───────────────────────────────────────────────────────────
INSERT IGNORE INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, appointment_mode, reason_for_visit, status, token_number)
SELECT p.patient_id, d.doctor_id, CURDATE(), '09:00:00', 'In-Person', 'Routine check-up', 'Scheduled', 1
FROM patients p, doctors d WHERE p.patient_number='PAT-1001' AND d.doctor_code=(SELECT MIN(doctor_code) FROM doctors);

INSERT IGNORE INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, appointment_mode, reason_for_visit, status, token_number)
SELECT p.patient_id, d.doctor_id, CURDATE(), '09:30:00', 'In-Person', 'Chest pain follow-up', 'Checked-In', 2
FROM patients p, doctors d WHERE p.patient_number='PAT-1002' AND d.doctor_code=(SELECT MIN(doctor_code) FROM doctors);

INSERT IGNORE INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, appointment_mode, reason_for_visit, status, token_number)
SELECT p.patient_id, d.doctor_id, CURDATE(), '10:00:00', 'In-Person', 'Knee pain', 'Completed', 3
FROM patients p, doctors d WHERE p.patient_number='PAT-1003' AND d.doctor_code=(SELECT MAX(doctor_code) FROM doctors);

INSERT IGNORE INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, appointment_mode, reason_for_visit, status, token_number)
SELECT p.patient_id, d.doctor_id, CURDATE(), '10:30:00', 'In-Person', 'Headache and dizziness', 'Scheduled', 1
FROM patients p, doctors d WHERE p.patient_number='PAT-1004' AND d.doctor_code=(SELECT doctor_code FROM doctors LIMIT 1 OFFSET 1);

INSERT IGNORE INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, appointment_mode, reason_for_visit, status, token_number)
SELECT p.patient_id, d.doctor_id, DATE_SUB(CURDATE(),INTERVAL 1 DAY), '11:00:00', 'In-Person', 'Diabetes management', 'Completed', 1
FROM patients p, doctors d WHERE p.patient_number='PAT-1005' AND d.doctor_code=(SELECT MIN(doctor_code) FROM doctors);

INSERT IGNORE INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, appointment_mode, reason_for_visit, status, token_number)
SELECT p.patient_id, d.doctor_id, DATE_ADD(CURDATE(),INTERVAL 1 DAY), '09:00:00', 'In-Person', 'Blood pressure check', 'Scheduled', 1
FROM patients p, doctors d WHERE p.patient_number='PAT-1006' AND d.doctor_code=(SELECT MIN(doctor_code) FROM doctors);

-- ─── DRUGS MASTER ───────────────────────────────────────────────────────────
INSERT IGNORE INTO drugs_master (generic_name, brand_name, form, strength) VALUES
('Paracetamol',      'Panadol',       'Tablet',   '500mg'),
('Amoxicillin',      'Amoxil',        'Capsule',  '250mg'),
('Metformin',        'Glucophage',    'Tablet',   '500mg'),
('Atorvastatin',     'Lipitor',       'Tablet',   '10mg'),
('Omeprazole',       'Losec',         'Capsule',  '20mg'),
('Amlodipine',       'Norvasc',       'Tablet',   '5mg'),
('Salbutamol',       'Ventolin',      'Syrup',    '2mg/5ml'),
('Ibuprofen',        'Brufen',        'Tablet',   '400mg'),
('Ciprofloxacin',    'Cifran',        'Tablet',   '500mg'),
('Diclofenac Sodium','Voltaren',      'Ointment', '1%');

-- ─── INVENTORY BATCHES ──────────────────────────────────────────────────────
INSERT IGNORE INTO inventory_batches (drug_id, batch_number, manufacturing_date, expiry_date, quantity_in_stock, purchase_price_lkr, selling_price_lkr, supplier_details)
SELECT drug_id, CONCAT('BATCH-',drug_id,'-001'), '2024-01-01', '2026-12-31',
  100 + (drug_id * 15), drug_id * 20.00, drug_id * 35.00, 'Lanka Pharma Distributors'
FROM drugs_master;

-- ─── LAB TESTS MASTER ───────────────────────────────────────────────────────
INSERT IGNORE INTO lab_tests_master (test_name, category, normal_range, unit, price_lkr) VALUES
('Full Blood Count',        'Hematology',      '4.5-11 x10^9/L',    'x10^9/L', 450.00),
('Blood Glucose (Fasting)', 'Biochemistry',    '70-100',             'mg/dL',   250.00),
('Lipid Profile',           'Biochemistry',    'LDL < 100 mg/dL',   'mg/dL',   600.00),
('Urine Full Report',       'Microbiology',    'No RBC/WBC',         '',        200.00),
('Thyroid Function (TSH)',  'Endocrinology',   '0.4-4.0',            'mIU/L',   800.00),
('HbA1c',                   'Biochemistry',    '< 5.7%',             '%',       750.00),
('Liver Function Test',     'Biochemistry',    'ALT 7-56 U/L',       'U/L',     900.00),
('Creatinine (Serum)',      'Nephrology',      '0.7-1.3',            'mg/dL',   350.00),
('ECG',                     'Cardiology',      'Normal Sinus Rhythm', '',       500.00),
('Chest X-Ray',             'Radiology',       'Normal',              '',       800.00);

-- ─── COMMUNICATION TEMPLATES ─────────────────────────────────────────────────
INSERT IGNORE INTO communication_templates (template_name, channel, content, is_active) VALUES
('Appointment Reminder SMS',  'SMS',      'MediCore: Reminder - You have an appointment on {date} at {time}. Please arrive 10 min early. Call 0112345678 to reschedule.', 1),
('Lab Result Ready SMS',      'SMS',      'MediCore: Your lab results for {test_name} are ready. Please collect from the lab or visit our portal.', 1),
('Appointment Reminder WA',   'WhatsApp', 'Hello {patient_name}, this is a reminder of your appointment at MediCore on {date} at {time}. Reply CONFIRM to confirm.', 1),
('Welcome Patient SMS',       'SMS',      'Welcome to MediCore, {patient_name}! Your patient ID is {patient_id}. Keep this for future reference.', 1),
('Bill Ready SMS',            'SMS',      'MediCore: Your invoice #{invoice_number} of Rs. {amount} is ready. Please proceed to the cashier.', 1);

-- ─── SYSTEM SETTINGS ─────────────────────────────────────────────────────────
INSERT IGNORE INTO system_settings (setting_key, setting_value, description) VALUES
('clinic_name',       'MediCore Clinic',         'Name of the clinic'),
('clinic_address',    '45 Hospital Road, Colombo 07', 'Clinic address'),
('clinic_phone',      '0112345678',              'Main contact number'),
('clinic_email',      'info@medicore.local',     'Clinic email'),
('currency',          'LKR',                     'Default currency'),
('tax_enabled',       'true',                    'Enable tax on invoices'),
('appointment_slot',  '30',                      'Appointment slot duration in minutes'),
('working_hours',     '08:00-17:00',             'Clinic working hours'),
('max_daily_tokens',  '50',                      'Max tokens per doctor per day');

-- ─── PHYSICAL QUEUES ─────────────────────────────────────────────────────────
INSERT IGNORE INTO physical_queues (patient_id, doctor_id, queue_date, queue_number, status)
SELECT a.patient_id, a.doctor_id, CURDATE(), a.token_number,
  CASE a.status WHEN 'Checked-In' THEN 'In Consultation' WHEN 'Completed' THEN 'Completed' ELSE 'Waiting' END
FROM appointments a WHERE a.appointment_date = CURDATE();

-- ─── INVOICES + ITEMS + PAYMENTS ─────────────────────────────────────────────
INSERT IGNORE INTO invoices (invoice_number, patient_id, appointment_id, subtotal, doctor_fee, hospital_fee, tax_amount, discount_amount, total_amount, status, created_by)
SELECT CONCAT('INV-26-',LPAD(a.appointment_id,4,'0')),
  a.patient_id, a.appointment_id,
  d.doctor_fee + d.hospital_fee, d.doctor_fee, d.hospital_fee,
  ROUND((d.doctor_fee + d.hospital_fee) * 0.00, 2), 0.00,
  d.doctor_fee + d.hospital_fee,
  CASE a.status WHEN 'Completed' THEN 'Paid' ELSE 'Pending' END,
  (SELECT user_id FROM users WHERE role='Receptionist' LIMIT 1)
FROM appointments a
JOIN doctors d ON d.doctor_id = a.doctor_id;

INSERT IGNORE INTO invoice_items (invoice_id, description, quantity, unit_price, line_total)
SELECT i.invoice_id, 'Doctor Consultation Fee', 1, i.doctor_fee, i.doctor_fee
FROM invoices i WHERE i.doctor_fee > 0;

INSERT IGNORE INTO invoice_items (invoice_id, description, quantity, unit_price, line_total)
SELECT i.invoice_id, 'Hospital Service Fee', 1, i.hospital_fee, i.hospital_fee
FROM invoices i WHERE i.hospital_fee > 0;

INSERT IGNORE INTO payments (invoice_id, amount_paid, payment_method, transaction_reference)
SELECT invoice_id, total_amount, 'Cash', CONCAT('TXN-', invoice_id)
FROM invoices WHERE status = 'Paid';

-- ─── PRESCRIPTIONS ───────────────────────────────────────────────────────────
INSERT IGNORE INTO prescriptions (prescription_code, appointment_id, patient_id, doctor_id, general_instructions)
SELECT CONCAT('RX-',LPAD(a.appointment_id,4,'0')), a.appointment_id, a.patient_id, a.doctor_id,
  'Take medications as directed. Drink plenty of water. Follow up in 2 weeks.'
FROM appointments a WHERE a.status = 'Completed';

INSERT IGNORE INTO prescription_items (prescription_id, drug_id, dosage, frequency, duration_days, special_instructions)
SELECT pr.prescription_id, dm.drug_id, '1 tablet', 'Twice daily', 7, 'Take after meals'
FROM prescriptions pr, drugs_master dm WHERE dm.generic_name = 'Paracetamol' LIMIT 5;

INSERT IGNORE INTO prescription_items (prescription_id, drug_id, dosage, frequency, duration_days, special_instructions)
SELECT pr.prescription_id, dm.drug_id, '1 capsule', 'Three times daily', 5, 'Complete full course'
FROM prescriptions pr, drugs_master dm WHERE dm.generic_name = 'Amoxicillin' LIMIT 5;

-- ─── PATIENT VITALS ──────────────────────────────────────────────────────────
INSERT IGNORE INTO patient_vitals (patient_id, blood_pressure, heart_rate, temperature, weight_kg, height_cm, recorded_by)
SELECT p.patient_id, '120/80', '72', 36.8, 68.5, 170.0,
  (SELECT user_id FROM users WHERE role='Nurse' LIMIT 1)
FROM patients p LIMIT 5;

-- ─── LAB ORDERS ──────────────────────────────────────────────────────────────
INSERT IGNORE INTO lab_orders (order_number, patient_id, requesting_doctor_id, appointment_id, status, notes)
SELECT CONCAT('LAB-',LPAD(a.appointment_id,4,'0')), a.patient_id, a.doctor_id, a.appointment_id,
  CASE a.status WHEN 'Completed' THEN 'Completed' ELSE 'Pending' END,
  'Standard diagnostic workup'
FROM appointments a LIMIT 4;

-- ─── LAB RESULTS ─────────────────────────────────────────────────────────────
INSERT IGNORE INTO lab_results (order_id, test_id, result_value, is_abnormal, entered_by)
SELECT lo.order_id, lt.test_id, '98 mg/dL', 0,
  (SELECT user_id FROM users WHERE role='LabTechnician' LIMIT 1)
FROM lab_orders lo, lab_tests_master lt WHERE lt.test_name='Blood Glucose (Fasting)' AND lo.status='Completed' LIMIT 2;

-- ─── CONSULTATIONS ───────────────────────────────────────────────────────────
INSERT IGNORE INTO consultations (appointment_id, patient_id, doctor_id, chief_complaint, clinical_notes, diagnosis)
SELECT a.appointment_id, a.patient_id, a.doctor_id, a.reason_for_visit,
  'Patient presents with reported symptoms. Vitals stable. Examination conducted.',
  'Assessment complete. Treatment plan initiated.'
FROM appointments a WHERE a.status = 'Completed';

-- ─── STAFF ATTENDANCE ────────────────────────────────────────────────────────
INSERT IGNORE INTO staff_attendance (staff_id, attendance_date, clock_in_time, clock_out_time, status)
SELECT user_id, CURDATE(), '08:00:00', '17:00:00', 'Present'
FROM users WHERE status = 'Active';

INSERT IGNORE INTO staff_attendance (staff_id, attendance_date, clock_in_time, clock_out_time, status)
SELECT user_id, DATE_SUB(CURDATE(),INTERVAL 1 DAY), '08:05:00', '17:10:00', 'Present'
FROM users WHERE status = 'Active';

-- ─── PAYROLL RECORDS ─────────────────────────────────────────────────────────
INSERT IGNORE INTO payroll_records (staff_id, payroll_month, payroll_year, base_salary_lkr, bonuses_lkr, deductions_lkr, net_pay_lkr, payment_status)
SELECT user_id, MONTH(CURDATE()), YEAR(CURDATE()),
  CASE role WHEN 'Doctor' THEN 150000 WHEN 'Nurse' THEN 55000 WHEN 'Pharmacist' THEN 65000 WHEN 'LabTechnician' THEN 60000 ELSE 45000 END,
  5000.00, 2000.00,
  CASE role WHEN 'Doctor' THEN 153000 WHEN 'Nurse' THEN 58000 WHEN 'Pharmacist' THEN 68000 WHEN 'LabTechnician' THEN 63000 ELSE 48000 END,
  'Pending'
FROM users WHERE status = 'Active' AND role != 'SuperAdmin';

-- ─── MEDICAL HISTORY ─────────────────────────────────────────────────────────
INSERT IGNORE INTO medical_history (patient_id, allergies, chronic_conditions, past_surgeries, family_history)
SELECT p.patient_id,
  ELT(p.patient_id % 4 + 1, 'Penicillin', 'None known', 'Aspirin', 'Sulfa drugs'),
  ELT(p.patient_id % 4 + 1, 'Hypertension, Diabetes Type 2', 'None', 'Asthma', 'Hyperlipidemia'),
  ELT(p.patient_id % 3 + 1, 'Appendectomy 2015', 'None', 'Tonsillectomy 2010'),
  ELT(p.patient_id % 3 + 1, 'Father: Hypertension', 'Mother: Diabetes', 'No significant family history')
FROM patients p;

-- ─── PATIENT INSURANCE ───────────────────────────────────────────────────────
INSERT IGNORE INTO patient_insurance (patient_id, provider_name, policy_number, expiry_date)
SELECT p.patient_id,
  ELT(p.patient_id % 3 + 1, 'AIA Insurance', 'Ceylinco Life', 'Union Assurance'),
  CONCAT('POL-', LPAD(p.patient_id, 6, '0')),
  DATE_ADD(CURDATE(), INTERVAL 1 YEAR)
FROM patients p WHERE p.patient_id % 2 = 0;

-- ─── COMMUNICATION LOGS ──────────────────────────────────────────────────────
INSERT IGNORE INTO communication_logs (patient_id, recipient_number, channel, direction, message_type, content, status)
SELECT p.patient_id, p.phone_number, 'SMS', 'Outbound', 'Appointment Reminder',
  CONCAT('MediCore: Reminder - You have an appointment today. Please arrive on time.'),
  'Sent'
FROM patients p LIMIT 5;

SET FOREIGN_KEY_CHECKS = 1;
SELECT 'Mock data inserted successfully!' AS result;
