CREATE TABLE combined_articles (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content VARCHAR NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    created_at VARCHAR(100),
    updated_at VARCHAR(100),
    version INTEGER NOT NULL DEFAULT 1,
    deleted_at VARCHAR(100)
)
