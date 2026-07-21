CREATE TABLE extended_orders (
id INTEGER AUTOINCREMENT PRIMARY KEY,
user_id INTEGER NOT NULL,
order_number VARCHAR(255) NOT NULL,
total_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
status VARCHAR(50) NOT NULL DEFAULT 'pending',
priority VARCHAR(50) NOT NULL DEFAULT 'medium',
region VARCHAR(50) NOT NULL DEFAULT 'default',
category VARCHAR(255),
product VARCHAR(255),
department VARCHAR(255),
year VARCHAR(10),
quarter VARCHAR(10),
created_at TIMESTAMP,
updated_at TIMESTAMP,
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
