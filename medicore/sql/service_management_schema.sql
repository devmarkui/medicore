-- Service Management Schema for Reception/Channeling Desk
-- Includes dynamic service categories and items

USE medicore;

-- Service Categories (tabs/groups)
CREATE TABLE IF NOT EXISTS service_categories (
    category_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(120) NOT NULL UNIQUE,
    icon_class VARCHAR(60),
    display_order INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active_order (is_active, display_order),
    INDEX idx_category_name (category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Service Items (individual services/products)
CREATE TABLE IF NOT EXISTS service_items (
    item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    item_code VARCHAR(64) NOT NULL UNIQUE,
    item_name VARCHAR(200) NOT NULL,
    category_id BIGINT UNSIGNED NOT NULL,
    price DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active_category (is_active, category_id),
    INDEX idx_item_code (item_code),
    INDEX idx_display_order (display_order),
    CONSTRAINT fk_service_items_category FOREIGN KEY (category_id)
        REFERENCES service_categories(category_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed default service categories
INSERT INTO service_categories (category_name, icon_class, display_order, is_active, description)
VALUES
    ('All Services', 'icon-grid', 0, TRUE, 'All available services'),
    ('OPD Consultation', 'icon-stethoscope', 1, TRUE, 'General and specialist consultations'),
    ('Laboratory', 'icon-flask', 2, TRUE, 'Laboratory tests and investigations'),
    ('Imaging', 'icon-image', 3, TRUE, 'X-ray, ultrasound, CT, MRI'),
    ('Pharmacy', 'icon-pill', 4, TRUE, 'Medications and drugs'),
    ('Procedures', 'icon-syringe', 5, TRUE, 'Minor and major procedures')
ON DUPLICATE KEY UPDATE display_order=VALUES(display_order);

-- Seed default service items
INSERT INTO service_items (item_code, item_name, category_id, price, is_active, display_order, description)
VALUES
    ('OPD001', 'General Consultation', 2, 500.00, TRUE, 1, 'Initial general practitioner consultation'),
    ('OPD002', 'Follow-up Consultation', 2, 300.00, TRUE, 2, 'Follow-up visit with same doctor'),
    ('OPD003', 'Specialist Consultation', 2, 1000.00, TRUE, 3, 'Specialist doctor consultation'),
    
    ('LAB001', 'Blood Test - CBC', 3, 450.00, TRUE, 1, 'Complete Blood Count'),
    ('LAB002', 'Blood Test - Lipid Profile', 3, 600.00, TRUE, 2, 'Cholesterol and triglycerides'),
    ('LAB003', 'Blood Test - Glucose', 3, 250.00, TRUE, 3, 'Fasting blood glucose'),
    ('LAB004', 'Urine Test', 3, 200.00, TRUE, 4, 'Complete urinalysis'),
    
    ('IMG001', 'X-Ray - Chest', 4, 800.00, TRUE, 1, 'Chest X-ray single view'),
    ('IMG002', 'X-Ray - Limb', 4, 600.00, TRUE, 2, 'Extremity X-ray'),
    ('IMG003', 'Ultrasound - Abdomen', 4, 1200.00, TRUE, 3, 'Abdominal ultrasound'),
    ('IMG004', 'Ultrasound - Thyroid', 4, 800.00, TRUE, 4, 'Thyroid ultrasound'),
    
    ('PHAR001', 'Medication Dispensing', 5, 100.00, TRUE, 1, 'Standard medication dispensing fee'),
    ('PHAR002', 'Intravenous Injection', 5, 250.00, TRUE, 2, 'IV medication administration'),
    
    ('PROC001', 'Vaccination', 6, 350.00, TRUE, 1, 'Standard vaccination service'),
    ('PROC002', 'Dressing & Wound Care', 6, 400.00, TRUE, 2, 'Wound dressing and management'),
    ('PROC003', 'Suture Removal', 6, 300.00, TRUE, 3, 'Suture removal service')
ON DUPLICATE KEY UPDATE price=VALUES(price);
