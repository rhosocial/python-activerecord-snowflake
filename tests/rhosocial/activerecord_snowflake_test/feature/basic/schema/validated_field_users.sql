CREATE TABLE validated_field_users (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    age INTEGER,
    balance NUMBER(10,2),
    credit_score INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    is_active BOOLEAN NOT NULL DEFAULT TRUE
)