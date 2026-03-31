USE medicore;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS full_name VARCHAR(200) NULL;

UPDATE users
SET full_name = CONCAT(first_name, ' ', last_name)
WHERE full_name IS NULL OR full_name = '';
