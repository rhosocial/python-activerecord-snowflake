CREATE TABLE event_tracking_models (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content VARCHAR NOT NULL,
    view_count INTEGER NOT NULL DEFAULT 0,
    last_viewed_at VARCHAR(100)
)
