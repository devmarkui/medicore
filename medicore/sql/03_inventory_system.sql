-- MediCore Inventory Management System - Database Schema Expansion
USE medicore;

-- 1. Inventory Items Table (General stock: consumables, lab supplies, drugs)
CREATE TABLE IF NOT EXISTS inventory_items (
    item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    item_name VARCHAR(200) NOT NULL,
    item_code VARCHAR(64) NOT NULL UNIQUE,
    category ENUM('Lab', 'Pharmacy', 'Procedure', 'General', 'Dental', 'Imaging') NOT NULL DEFAULT 'General',
    unit VARCHAR(40) NOT NULL DEFAULT 'pcs', -- pcs, ml, box, pkt
    quantity_on_hand INT NOT NULL DEFAULT 0,
    minimum_stock_level INT NOT NULL DEFAULT 10,
    buying_price DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    expiry_date DATE NULL,
    batch_number VARCHAR(64) NULL,
    supplier_info TEXT NULL,
    status ENUM('Active', 'Inactive') NOT NULL DEFAULT 'Active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_item_status (status),
    INDEX idx_item_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Service-to-Inventory Mapping (usage per service)
CREATE TABLE IF NOT EXISTS service_inventory_mapping (
    mapping_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    service_item_id BIGINT UNSIGNED NOT NULL, -- References service_items.id
    inventory_item_id BIGINT UNSIGNED NOT NULL,
    quantity_required DECIMAL(10,2) NOT NULL DEFAULT 1.00,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_service_item_mapping (service_item_id, inventory_item_id),
    CONSTRAINT fk_mapping_inventory FOREIGN KEY (inventory_item_id)
        REFERENCES inventory_items(item_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Stock Transactions Log (Audit Trail)
CREATE TABLE IF NOT EXISTS inventory_transactions (
     transaction_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
     inventory_item_id BIGINT UNSIGNED NOT NULL,
     transaction_type ENUM('IN', 'OUT', 'ADJUST', 'USED', 'RETURN') NOT NULL,
     quantity DECIMAL(12,2) NOT NULL,
     reference_type ENUM('Bill', 'Lab', 'Pharmacy', 'Manual', 'Purchase') NOT NULL DEFAULT 'Manual',
     reference_id VARCHAR(64) NULL, -- Invoice Number or Lab Order ID
     note TEXT NULL,
     created_by BIGINT UNSIGNED NOT NULL,
     created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
     CONSTRAINT fk_trans_item FOREIGN KEY (inventory_item_id)
         REFERENCES inventory_items(item_id) ON DELETE RESTRICT ON UPDATE CASCADE,
     CONSTRAINT fk_trans_user FOREIGN KEY (created_by)
         REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed some basic inventory items
INSERT IGNORE INTO inventory_items (item_name, item_code, category, unit, quantity_on_hand, minimum_stock_level)
VALUES 
    ('Vacutainer Tube (CBC)', 'INV-LAB-001', 'Lab', 'pcs', 500, 50),
    ('Disposable Syringe (5ml)', 'INV-GEN-002', 'General', 'pcs', 1000, 100),
    ('Latex Gloves (Medium)', 'INV-GEN-003', 'General', 'box', 50, 5),
    ('Cotton Roll (500g)', 'INV-GEN-004', 'General', 'pkt', 20, 2),
    ('Spirit / Alcohol Swab', 'INV-GEN-005', 'General', 'pcs', 2000, 200),
    ('Glucose Reagent', 'INV-LAB-006', 'Lab', 'ml', 1000, 100);
