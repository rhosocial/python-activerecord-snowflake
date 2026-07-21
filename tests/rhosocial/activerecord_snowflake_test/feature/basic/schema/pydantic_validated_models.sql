-- Snowflake version of the pydantic_validated_models table schema

CREATE TABLE pydantic_validated_models (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    code VARCHAR(32),
    quantity INTEGER,
    step_count INTEGER,
    price DECIMAL(10, 2),
    start_at TIMESTAMP,
    end_at TIMESTAMP,
    status VARCHAR(32),
    normalized_name VARCHAR(50),
    created_token VARCHAR(255)
);
