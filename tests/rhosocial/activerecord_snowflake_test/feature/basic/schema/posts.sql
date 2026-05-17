CREATE TABLE posts (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    author INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    content VARCHAR,
    published_at VARCHAR(100),
    published BOOLEAN DEFAULT FALSE,
    created_at VARCHAR(100),
    updated_at VARCHAR(100)
)