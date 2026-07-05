CREATE TABLE nodes (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    parent_id INTEGER,
    value DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    created_at VARCHAR(100),
    updated_at VARCHAR(100)
)
