USE medicore;

CREATE TABLE IF NOT EXISTS roles (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(60) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO roles (role_name, is_active) VALUES
    ('SuperAdmin', TRUE),
    ('CenterAdmin', TRUE),
    ('Doctor', TRUE),
    ('Nurse', TRUE),
    ('Receptionist', TRUE),
    ('Pharmacist', TRUE),
    ('LabTechnician', TRUE);

ALTER TABLE users
    ADD COLUMN username VARCHAR(120) NOT NULL DEFAULT '',
    ADD COLUMN role_id BIGINT UNSIGNED NULL,
    ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN id BIGINT UNSIGNED GENERATED ALWAYS AS (user_id) STORED;

UPDATE users
SET username = email
WHERE username = '';

UPDATE users u
INNER JOIN roles r ON r.role_name = u.role
SET u.role_id = r.id
WHERE u.role_id IS NULL;

UPDATE users
SET is_active = (status = 'Active');

ALTER TABLE users
    ADD UNIQUE KEY uq_users_username (username),
    ADD UNIQUE KEY uq_users_id (id),
    ADD CONSTRAINT fk_users_role
        FOREIGN KEY (role_id) REFERENCES roles(id)
        ON DELETE SET NULL ON UPDATE CASCADE;
