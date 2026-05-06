-- MediCore Pharmacy Publishing Workflow - Migration
-- Run this once against the medicore database.
USE medicore;

-- 1. Add linked_inventory_item_id to service_items
--    This is the FK that links a billing-facing pharmacy item back to its inventory master.
ALTER TABLE service_items
    ADD COLUMN IF NOT EXISTS linked_inventory_item_id BIGINT UNSIGNED NULL DEFAULT NULL
        COMMENT 'References inventory_items.item_id — only set for Pharmacy items'
    AFTER description,
    ADD INDEX IF NOT EXISTS idx_service_linked_inv (linked_inventory_item_id);

-- 2. Add opening_stock_quantity alias support to inventory_items
--    quantity_on_hand already handles this; but we need to ensure the column also stores
--    the initial opening value used at creation time.
--    We add a meta column to record what the opening stock was.
ALTER TABLE inventory_items
    ADD COLUMN IF NOT EXISTS opening_stock_quantity INT NOT NULL DEFAULT 0
        COMMENT 'Initial stock quantity entered at creation time'
    AFTER item_code;

-- 3. Ensure usage_mode column exists (was added in 04_inventory_expansion.sql; safe to re-run).
ALTER TABLE inventory_items
    MODIFY COLUMN usage_mode ENUM('Internal', 'Sale', 'Both') NOT NULL DEFAULT 'Internal';

-- 4. Add FK constraint for linked_inventory_item_id (if not already present)
-- We do this conditionally to avoid errors on re-run.
SET @fk_exists = (
    SELECT COUNT(*)
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'service_items'
      AND CONSTRAINT_NAME = 'fk_service_linked_inventory'
);

-- Use a stored procedure to conditionally add FK
DROP PROCEDURE IF EXISTS _add_fk_if_missing;
DELIMITER //
CREATE PROCEDURE _add_fk_if_missing()
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.TABLE_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE()
          AND TABLE_NAME = 'service_items'
          AND CONSTRAINT_NAME = 'fk_service_linked_inventory'
    ) THEN
        ALTER TABLE service_items
            ADD CONSTRAINT fk_service_linked_inventory
            FOREIGN KEY (linked_inventory_item_id)
            REFERENCES inventory_items(item_id)
            ON DELETE SET NULL ON UPDATE CASCADE;
    END IF;
END //
DELIMITER ;
CALL _add_fk_if_missing();
DROP PROCEDURE IF EXISTS _add_fk_if_missing;
