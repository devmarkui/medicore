-- MediCore Inventory - Stock Batches for per-batch pricing & FIFO
-- Run after: 04_inventory_expansion.sql
USE medicore;

-- 1. Stock Batches table — one row per stock-in event
CREATE TABLE IF NOT EXISTS stock_batches (
    batch_id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    inventory_item_id  BIGINT UNSIGNED NOT NULL,
    batch_number       VARCHAR(64) NULL,
    quantity_received  DECIMAL(12,2) NOT NULL,
    quantity_remaining DECIMAL(12,2) NOT NULL,
    buying_price       DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    selling_price      DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    expiry_date        DATE NULL,
    supplier_id        BIGINT UNSIGNED NULL,
    received_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by         BIGINT UNSIGNED NULL,
    INDEX idx_batch_item (inventory_item_id),
    INDEX idx_batch_remaining (inventory_item_id, quantity_remaining),
    INDEX idx_batch_fifo (inventory_item_id, received_at),
    CONSTRAINT fk_batch_item FOREIGN KEY (inventory_item_id)
        REFERENCES inventory_items(item_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
