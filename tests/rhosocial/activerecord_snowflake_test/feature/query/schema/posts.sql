CREATE TABLE posts (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    content VARCHAR,
    status VARCHAR(50) NOT NULL DEFAULT 'published',
    created_at VARCHAR(100),
    updated_at VARCHAR(100)
)
