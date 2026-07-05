CREATE TABLE json_users (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    age INTEGER,
    created_at VARCHAR(100),
    updated_at VARCHAR(100),
    settings VARIANT,
    tags VARIANT,
    profile VARIANT,
    roles VARIANT,
    scores VARIANT,
    subscription VARIANT,
    preferences VARIANT
)
