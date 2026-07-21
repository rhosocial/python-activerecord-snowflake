CREATE TABLE extended_order_items (
id INTEGER AUTOINCREMENT PRIMARY KEY,
order_id INTEGER NOT NULL,
product_name VARCHAR(255) NOT NULL,
quantity INTEGER NOT NULL DEFAULT 1,
price DECIMAL(10,2) NOT NULL,
category VARCHAR(255),
region VARCHAR(50),
created_at TIMESTAMP,
updated_at TIMESTAMP,
FOREIGN KEY (order_id) REFERENCES extended_orders(id) ON DELETE CASCADE
);
