-- Bảng Users (Không thay đổi)
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    user_name VARCHAR(20) NOT NULL
);

-- Bảng Categories 
CREATE TYPE category_enum AS ENUM ('income', 'expense');

CREATE TABLE bills (
    bill_id SERIAL PRIMARY KEY,
    bill_date DATE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    merchant_name VARCHAR(128),
    
    -- Cột mới thay thế cho bảng categories
    category_name VARCHAR(50) NOT NULL, -- Tên danh mục lưu trực tiếp
    category_type category_enum NOT NULL, -- Loại thu/chi
    
    total_amount NUMERIC(16,2) NOT NULL,
    note TEXT
);

-- Add indexes for performance
CREATE INDEX idx_bills_date ON bills(bill_date);
CREATE INDEX idx_bills_user ON bills(user_id);
-- Index cho cột category_name mới để tăng tốc độ lọc và nhóm
CREATE INDEX idx_bills_category_name ON bills(category_name);


-- Bảng Idempotency keys (Không thay đổi)
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW()
);