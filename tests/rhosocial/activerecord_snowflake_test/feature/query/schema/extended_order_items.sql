CREATE TABLE extended_order_items (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    price DECIMAL(10,2) NOT NULL,
    category VARCHAR(255),
    region VARCHAR(50),
    created_at VARCHAR(100),
    updated_at VARCHAR(100)
)
