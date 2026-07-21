CREATE TABLE profiles (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    bio VARCHAR,
    avatar_url VARCHAR(512),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
