CREATE TABLE type_tests (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    string_field VARCHAR(255) NOT NULL DEFAULT 'test string',
    int_field INTEGER NOT NULL DEFAULT 42,
    float_field FLOAT NOT NULL DEFAULT 3.14,
    decimal_field DOUBLE NOT NULL DEFAULT 10.99,
    bool_field BOOLEAN NOT NULL DEFAULT TRUE,
    datetime_field VARCHAR NOT NULL,
    json_field VARIANT,
    nullable_field VARCHAR(255)
)