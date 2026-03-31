USE medicore;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS username VARCHAR(120) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS role_id BIGINT UNSIGNED NULL,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS id BIGINT UNSIGNED NULL;

UPDATE users
SET username = email
WHERE username = '' OR username IS NULL;

UPDATE users u
INNER JOIN roles r ON r.role_name = u.role
SET u.role_id = r.id
WHERE u.role_id IS NULL;

UPDATE users
SET is_active = (status = 'Active')
WHERE is_active IS NULL OR is_active IN (0, 1);

ALTER TABLE users
    ADD UNIQUE KEY IF NOT EXISTS uq_users_username (username),
    ADD UNIQUE KEY IF NOT EXISTS uq_users_id (id),
    ADD CONSTRAINT fk_users_role
        FOREIGN KEY (role_id) REFERENCES roles(id)
        ON DELETE SET NULL ON UPDATE CASCADE;

UPDATE users
SET id = user_id
WHERE id IS NULL;

DROP TRIGGER IF EXISTS users_sync_id;
DROP TRIGGER IF EXISTS users_sync_id_update;

DELIMITER $$
CREATE TRIGGER users_sync_id
AFTER INSERT ON users
FOR EACH ROW
BEGIN
    UPDATE users SET id = NEW.user_id WHERE user_id = NEW.user_id AND id IS NULL;
END$$

CREATE TRIGGER users_sync_id_update
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    IF NEW.id IS NULL OR NEW.id <> NEW.user_id THEN
        UPDATE users SET id = NEW.user_id WHERE user_id = NEW.user_id;
    END IF;
END$$
DELIMITER ;
