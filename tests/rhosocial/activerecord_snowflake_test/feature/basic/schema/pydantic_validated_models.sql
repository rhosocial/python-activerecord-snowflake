CREATE TABLE pydantic_validated_models (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    code VARCHAR(32),
    quantity INTEGER,
    step_count INTEGER,
    price DOUBLE,
    start_at VARCHAR(100),
    end_at VARCHAR(100),
    status VARCHAR(32),
    normalized_name VARCHAR(50),
    created_token VARCHAR(255)
)
