-- ==============================
-- MediCore Users Table Creation
-- Supports RBAC, Argon2, and 2FA
-- ==============================
CREATE TABLE IF NOT EXISTS users (
    user_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    email VARCHAR(190) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(25) DEFAULT NULL,
    role ENUM('SuperAdmin','CenterAdmin','Doctor','Nurse','Receptionist','Pharmacist','LabTechnician')
         NOT NULL DEFAULT 'Receptionist',
    status ENUM('Active','Inactive') NOT NULL DEFAULT 'Active',
    two_factor_secret VARCHAR(32) DEFAULT NULL,
    is_2fa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL DEFAULT NULL,
    PRIMARY KEY (user_id),
    INDEX idx_users_email (email)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- Bootstrap SuperAdmin user (CHANGE PASSWORD IMMEDIATELY)
-- =====================================================
INSERT INTO users (
    email,
    password_hash,
    first_name,
    last_name,
    phone_number,
    role,
    status,
    two_factor_secret,
    is_2fa_enabled
) VALUES (
    'admin@medicore.local',
    '$argon2id$v=19$m=65536,t=4,p=2$VGVzdFNhbHQAAAAAAAAAAA$gJmJpF1s/HF2gGfY0BZ6yQCq7FJrjsF1n9wgVFeqkeU',
    'System',
    'Admin',
    '+94112223333',
    'SuperAdmin',
    'Active',
    NULL,
    FALSE
);
