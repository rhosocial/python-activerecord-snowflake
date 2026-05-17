CREATE TABLE mixed_annotation_items (
    id INTEGER AUTOINCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    tags VARCHAR,
    meta VARCHAR,
    description VARCHAR,
    status VARCHAR
)