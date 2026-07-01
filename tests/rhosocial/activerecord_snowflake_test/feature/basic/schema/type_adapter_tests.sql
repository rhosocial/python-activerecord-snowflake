CREATE TABLE type_adapter_tests (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    optional_name VARCHAR(255),
    optional_age INTEGER,
    last_login VARCHAR(100),
    is_premium BOOLEAN,
    unsupported_union VARCHAR(255),
    custom_bool VARCHAR(3),
    optional_custom_bool VARCHAR(3)
)