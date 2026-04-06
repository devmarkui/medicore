USE medicore;

ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS birth_year SMALLINT NULL AFTER date_of_birth;

ALTER TABLE patients
    MODIFY date_of_birth DATE NULL;
