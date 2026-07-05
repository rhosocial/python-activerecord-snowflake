CREATE TABLE order_items (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    created_at VARCHAR(100),
    updated_at VARCHAR(100)
)
