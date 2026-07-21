CREATE TABLE json_users (
id INTEGER AUTOINCREMENT PRIMARY KEY,
username VARCHAR(255) NOT NULL,
email VARCHAR(255) NOT NULL,
age INTEGER,
created_at TIMESTAMP,
updated_at TIMESTAMP,
settings VARIANT,
tags VARIANT,
profile VARIANT,
roles VARIANT,
scores VARIANT,
subscription VARIANT,
preferences VARIANT
);
