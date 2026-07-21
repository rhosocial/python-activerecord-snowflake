# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/conftest.py
"""
Pytest fixtures for Snowflake introspection tests.

This module provides fixtures for testing database introspection
functionality with Snowflake backends.
"""

import pytest
import pytest_asyncio


# SQL script for creating test tables
_TABLES_SQL = """
    SET FOREIGN_KEY_CHECKS = 0;
    DROP TABLE IF EXISTS post_tags;
    DROP TABLE IF EXISTS posts;
    DROP TABLE IF EXISTS tags;
    DROP TABLE IF EXISTS users;
    SET FOREIGN_KEY_CHECKS = 1;

    CREATE TABLE users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(255) NOT NULL,
        age INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE INDEX idx_users_email (email),
        INDEX idx_users_name_age (name, age)
    ) ENGINE=InnoDB;

    CREATE TABLE posts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        content TEXT,
        user_id INT NOT NULL,
        status ENUM('draft', 'published', 'archived') DEFAULT 'draft',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_posts_user_id (user_id),
        CONSTRAINT fk_posts_user
            FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
    ) ENGINE=InnoDB;

    CREATE TABLE tags (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(50) NOT NULL UNIQUE
    ) ENGINE=InnoDB;

    CREATE TABLE post_tags (
        post_id INT NOT NULL,
        tag_id INT NOT NULL,
        PRIMARY KEY (post_id, tag_id),
        CONSTRAINT fk_post_tags_post
            FOREIGN KEY (post_id)
            REFERENCES posts(id)
            ON DELETE CASCADE,
        CONSTRAINT fk_post_tags_tag
            FOREIGN KEY (tag_id)
            REFERENCES tags(id)
            ON DELETE CASCADE
    ) ENGINE=InnoDB;
"""

_CLEANUP_TABLES_SQL = """
    SET FOREIGN_KEY_CHECKS = 0;
    DROP TABLE IF EXISTS post_tags;
    DROP TABLE IF EXISTS posts;
    DROP TABLE IF EXISTS tags;
    DROP TABLE IF EXISTS users;
    SET FOREIGN_KEY_CHECKS = 1;
"""

_VIEW_SQL = """
    SET FOREIGN_KEY_CHECKS = 0;
    DROP VIEW IF EXISTS user_summary;
    DROP TABLE IF EXISTS user_stats;
    DROP TABLE IF EXISTS users;
    SET FOREIGN_KEY_CHECKS = 1;

    CREATE TABLE users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(255) NOT NULL
    ) ENGINE=InnoDB;

    CREATE TABLE user_stats (
        user_id INT PRIMARY KEY,
        post_count INT DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    ) ENGINE=InnoDB;

    CREATE VIEW user_summary AS
    SELECT u.id, u.name, u.email, COALESCE(s.post_count, 0) as post_count
    FROM users u
    LEFT JOIN user_stats s ON u.id = s.user_id;
"""

_CLEANUP_VIEW_SQL = """
    SET FOREIGN_KEY_CHECKS = 0;
    DROP VIEW IF EXISTS user_summary;
    DROP TABLE IF EXISTS user_stats;
    DROP TABLE IF EXISTS users;
    SET FOREIGN_KEY_CHECKS = 1;
"""

_TRIGGER_SQL = """
    SET FOREIGN_KEY_CHECKS = 0;
    DROP TRIGGER IF EXISTS update_user_timestamp;
    DROP TABLE IF EXISTS users;
    SET FOREIGN_KEY_CHECKS = 1;

    CREATE TABLE users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB;

    CREATE TRIGGER update_user_timestamp
    BEFORE UPDATE ON users
    FOR EACH ROW
    SET NEW.updated_at = CURRENT_TIMESTAMP;
"""

_CLEANUP_TRIGGER_SQL = """
    SET FOREIGN_KEY_CHECKS = 0;
    DROP TRIGGER IF EXISTS update_user_timestamp;
    DROP TABLE IF EXISTS users;
    SET FOREIGN_KEY_CHECKS = 1;
"""


@pytest.fixture(scope="function")
def backend_with_tables(snowflake_backend):
    """Fixture providing backend with test tables created."""
    snowflake_backend.introspector.clear_cache()
    snowflake_backend.executescript(_TABLES_SQL)
    yield snowflake_backend
    try:
        snowflake_backend.introspector.clear_cache()
        snowflake_backend.executescript(_CLEANUP_TABLES_SQL)
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def async_backend_with_tables(async_snowflake_backend):
    """Async fixture providing backend with test tables created."""
    async_snowflake_backend.introspector.clear_cache()
    await async_snowflake_backend.executescript(_TABLES_SQL)
    yield async_snowflake_backend
    try:
        async_snowflake_backend.introspector.clear_cache()
        await async_snowflake_backend.executescript(_CLEANUP_TABLES_SQL)
    except Exception:
        pass


@pytest.fixture(scope="function")
def backend_with_view(snowflake_backend):
    """Fixture providing backend with a test view."""
    snowflake_backend.introspector.clear_cache()
    snowflake_backend.executescript(_VIEW_SQL)
    yield snowflake_backend
    try:
        snowflake_backend.introspector.clear_cache()
        snowflake_backend.executescript(_CLEANUP_VIEW_SQL)
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def async_backend_with_view(async_snowflake_backend):
    """Async fixture providing backend with a test view."""
    async_snowflake_backend.introspector.clear_cache()
    await async_snowflake_backend.executescript(_VIEW_SQL)
    yield async_snowflake_backend
    try:
        async_snowflake_backend.introspector.clear_cache()
        await async_snowflake_backend.executescript(_CLEANUP_VIEW_SQL)
    except Exception:
        pass


@pytest.fixture(scope="function")
def backend_with_trigger(snowflake_backend):
    """Fixture providing backend with a test trigger."""
    snowflake_backend.introspector.clear_cache()
    snowflake_backend.executescript(_TRIGGER_SQL)
    yield snowflake_backend
    try:
        snowflake_backend.introspector.clear_cache()
        snowflake_backend.executescript(_CLEANUP_TRIGGER_SQL)
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def async_backend_with_trigger(async_snowflake_backend):
    """Async fixture providing backend with a test trigger."""
    async_snowflake_backend.introspector.clear_cache()
    await async_snowflake_backend.executescript(_TRIGGER_SQL)
    yield async_snowflake_backend
    try:
        async_snowflake_backend.introspector.clear_cache()
        await async_snowflake_backend.executescript(_CLEANUP_TRIGGER_SQL)
    except Exception:
        pass
