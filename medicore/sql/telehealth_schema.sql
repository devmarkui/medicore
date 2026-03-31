ALTER TABLE appointments
    ADD COLUMN appointment_mode ENUM('In-Person', 'Online') NOT NULL DEFAULT 'In-Person',
    ADD COLUMN telehealth_link VARCHAR(255) NULL;
