CREATE TABLE profiles (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    bio VARCHAR,
    avatar_url VARCHAR,
    created_at VARCHAR(100),
    updated_at VARCHAR(100)
)
