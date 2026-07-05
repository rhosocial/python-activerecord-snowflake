CREATE TABLE timestamped_posts (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content VARCHAR NOT NULL,
    created_at VARCHAR(100),
    updated_at VARCHAR(100)
)
