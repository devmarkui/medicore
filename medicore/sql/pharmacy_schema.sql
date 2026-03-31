CREATE TABLE IF NOT EXISTS inventory_batches (
    batch_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    drug_id BIGINT NOT NULL,
    batch_number VARCHAR(60) NOT NULL,
    manufacturing_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    quantity_in_stock INT NOT NULL DEFAULT 0,
    purchase_price_lkr DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    selling_price_lkr DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    supplier_details VARCHAR(255) NULL,
    INDEX idx_inventory_batches_drug (drug_id),
    INDEX idx_inventory_batches_expiry (expiry_date),
    CONSTRAINT fk_inventory_batches_drug
        FOREIGN KEY (drug_id) REFERENCES drugs_master(drug_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS pharmacy_sales (
    sale_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id VARCHAR(36) NULL,
    prescription_id VARCHAR(20) NULL,
    total_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    payment_method ENUM('Cash', 'Card') NOT NULL,
    sale_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sold_by BIGINT NOT NULL,
    INDEX idx_pharmacy_sales_patient (patient_id),
    INDEX idx_pharmacy_sales_prescription (prescription_id),
    CONSTRAINT fk_pharmacy_sales_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_pharmacy_sales_prescription
        FOREIGN KEY (prescription_id) REFERENCES prescriptions(prescription_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_pharmacy_sales_sold_by
        FOREIGN KEY (sold_by) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS pharmacy_sale_items (
    item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sale_id BIGINT NOT NULL,
    batch_id BIGINT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    subtotal DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    INDEX idx_pharmacy_sale_items_sale (sale_id),
    CONSTRAINT fk_pharmacy_sale_items_sale
        FOREIGN KEY (sale_id) REFERENCES pharmacy_sales(sale_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_pharmacy_sale_items_batch
        FOREIGN KEY (batch_id) REFERENCES inventory_batches(batch_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
);

ALTER TABLE prescriptions
    ADD COLUMN status ENUM('Pending', 'Dispensed') NOT NULL DEFAULT 'Pending';
