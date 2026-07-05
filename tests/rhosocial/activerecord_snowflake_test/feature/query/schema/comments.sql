CREATE TABLE comments (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    content VARCHAR,
    is_hidden BOOLEAN DEFAULT FALSE,
    created_at VARCHAR(100),
    updated_at VARCHAR(100)
)
