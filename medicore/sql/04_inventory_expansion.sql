-- MediCore Inventory Management System - Database Expansion
USE medicore;

-- 1. Inventory Categories
CREATE TABLE IF NOT EXISTS inventory_categories (
    category_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    supplier_name VARCHAR(200) NOT NULL,
    contact_person VARCHAR(100),
    email VARCHAR(150),
    phone VARCHAR(20),
    address TEXT,
    tax_number VARCHAR(50),
    status ENUM('Active', 'Inactive') NOT NULL DEFAULT 'Active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Modify Inventory Items
ALTER TABLE inventory_items 
    ADD COLUMN subcategory_id BIGINT UNSIGNED NULL AFTER category,
    ADD COLUMN brand_name VARCHAR(100) NULL AFTER item_name,
    ADD COLUMN generic_name VARCHAR(200) NULL AFTER brand_name,
    ADD COLUMN max_stock_level INT NULL AFTER minimum_stock_level,
    ADD COLUMN selling_price DECIMAL(12,2) NOT NULL DEFAULT 0.00 AFTER buying_price,
    ADD COLUMN supplier_id BIGINT UNSIGNED NULL AFTER batch_number,
    ADD COLUMN storage_location VARCHAR(100) NULL AFTER supplier_id,
    ADD COLUMN is_saleable BOOLEAN NOT NULL DEFAULT FALSE AFTER status,
    ADD COLUMN is_consumable BOOLEAN NOT NULL DEFAULT TRUE AFTER is_saleable,
    ADD COLUMN usage_mode ENUM('Internal', 'Sale', 'Both') NOT NULL DEFAULT 'Internal' AFTER is_consumable,
    ADD COLUMN track_expiry BOOLEAN NOT NULL DEFAULT TRUE AFTER usage_mode,
    ADD COLUMN created_by BIGINT UNSIGNED NULL AFTER updated_at,
    ADD COLUMN updated_by BIGINT UNSIGNED NULL AFTER created_by;

-- 4. Modify Service Inventory Mapping
ALTER TABLE service_inventory_mapping 
    ADD COLUMN usage_stage ENUM('on_bill', 'on_sample_collection', 'on_completion', 'on_dispense') NOT NULL DEFAULT 'on_completion' AFTER quantity_required,
    ADD COLUMN is_required BOOLEAN NOT NULL DEFAULT TRUE AFTER usage_stage,
    ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

-- 5. Modify Inventory Transactions
ALTER TABLE inventory_transactions 
    MODIFY COLUMN transaction_type ENUM('IN', 'OUT', 'ADJUST', 'USED', 'RETURN', 'SALE', 'DAMAGE', 'EXPIRED', 'REVERSAL') NOT NULL,
    ADD COLUMN before_qty DECIMAL(12,2) NOT NULL DEFAULT 0.00 AFTER quantity,
    ADD COLUMN after_qty DECIMAL(12,2) NOT NULL DEFAULT 0.00 AFTER before_qty,
    ADD COLUMN batch_number VARCHAR(64) NULL AFTER reference_id;

-- Seed initial categories
INSERT IGNORE INTO inventory_categories (category_name) VALUES 
('Lab Consumables'), ('Pharmacy'), ('Procedure Supplies'), 
('Imaging Supplies'), ('General Consumables'), ('Medicines'), 
('Equipment Accessories'), ('Stationery');

-- Update existing items to use categories if needed (Optional: link to ID if I switch category to category_id)
-- Note: keeping it as ENUM for now or allowing VARCHAR for compatibility if needed.
-- For a strict system, I would shift category to category_id. 
-- Let's do that for the "true clinic system".

ALTER TABLE inventory_items MODIFY COLUMN category VARCHAR(100); -- temporarily allow VARCHAR
