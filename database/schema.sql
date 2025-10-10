-- Linking table: user_categories (many-to-many between users and categories)
CREATE TABLE user_categories (
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(category_id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, category_id)
);

CREATE TABLE bills (
    bill_id SERIAL PRIMARY KEY,
    bill_date DATE NOT NULL,
    user_id INTEGER NOT NULL FOREIGN KEY REFERENCES users(user_id),
    merchant_name VARCHAR(128),
    category_name VARCHAR(64) NOT NULL,
    total_amount NUMERIC(16,2) NOT NULL,
    note TEXT
);

-- Add indexes for performance
CREATE INDEX idx_bills_date ON bills(bill_date);
CREATE INDEX idx_bills_category ON bills(category_name);

-- Users table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    user_name VARCHAR(20) NOT NULL
);

-- Categories table
CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(20) NOT NULL,
    user_id INTEGER REFERENCES users(user_id),
    category_type VARCHAR(20)
);
