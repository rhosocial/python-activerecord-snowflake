# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_introspection_triggers.py
"""
Tests for Snowflake trigger introspection.

This module tests the list_triggers and get_trigger_info methods
for retrieving trigger metadata.
"""

import pytest

from rhosocial.activerecord.backend.introspection.types import (
    TriggerInfo,
)


class TestListTriggers:
    """Tests for list_triggers method."""

    def test_list_triggers_empty_database(self, snowflake_backend_single):
        """Test list_triggers on database without triggers."""
        triggers = snowflake_backend_single.introspector.list_triggers()

        assert isinstance(triggers, list)
        # May have system triggers, just verify it returns a list

    def test_list_triggers_with_trigger(self, backend_with_trigger):
        """Test list_triggers returns created triggers."""
        triggers = backend_with_trigger.introspector.list_triggers()

        trigger_names = [t.name for t in triggers]
        assert "update_user_timestamp" in trigger_names

    def test_list_triggers_returns_trigger_info(self, backend_with_trigger):
        """Test that list_triggers returns TriggerInfo objects."""
        triggers = backend_with_trigger.introspector.list_triggers()

        for trigger in triggers:
            assert isinstance(trigger, TriggerInfo)

    def test_list_triggers_caching(self, backend_with_trigger):
        """Test that trigger list is cached."""
        triggers1 = backend_with_trigger.introspector.list_triggers()
        triggers2 = backend_with_trigger.introspector.list_triggers()

        # Should return the same cached list
        assert triggers1 is triggers2

    def test_list_triggers_filter_by_table(self, backend_with_trigger):
        """Test filtering triggers by table."""
        triggers = backend_with_trigger.introspector.list_triggers(table_name="users")

        for trigger in triggers:
            assert trigger.table_name == "users"


class TestGetTriggerInfo:
    """Tests for get_trigger_info method."""

    def test_get_trigger_info_existing(self, backend_with_trigger):
        """Test get_trigger_info for existing trigger."""
        trigger = backend_with_trigger.introspector.get_trigger_info("update_user_timestamp")

        assert trigger is not None
        assert isinstance(trigger, TriggerInfo)
        assert trigger.name == "update_user_timestamp"

    def test_get_trigger_info_nonexistent(self, backend_with_trigger):
        """Test get_trigger_info for non-existent trigger."""
        trigger = backend_with_trigger.introspector.get_trigger_info("nonexistent")

        assert trigger is None

    def test_get_trigger_info_table_name(self, backend_with_trigger):
        """Test that table_name is correctly set."""
        trigger = backend_with_trigger.introspector.get_trigger_info("update_user_timestamp")

        assert trigger is not None
        assert trigger.table_name == "users"


class TestTriggerDetails:
    """Tests for detailed trigger information."""

    def test_multiple_triggers(self, backend_with_trigger):
        """Test multiple triggers on same table."""
        backend_with_trigger.executescript("""
            CREATE TRIGGER before_user_insert
            BEFORE INSERT ON users
            FOR EACH ROW
            SET NEW.name = UPPER(NEW.name);

            CREATE TRIGGER after_user_delete
            AFTER DELETE ON users
            FOR EACH ROW
            INSERT INTO audit_log (action, table_name) VALUES ('DELETE', 'users');
        """)

        triggers = backend_with_trigger.introspector.list_triggers()

        trigger_names = {t.name for t in triggers}
        assert "update_user_timestamp" in trigger_names
        assert "before_user_insert" in trigger_names
        assert "after_user_delete" in trigger_names

        backend_with_trigger.executescript("""
            DROP TRIGGER IF EXISTS before_user_insert;
            DROP TRIGGER IF EXISTS after_user_delete;
            DROP TABLE IF EXISTS audit_log;
        """)

    def test_trigger_timing(self, backend_with_trigger):
        """Test trigger timing detection."""
        trigger = backend_with_trigger.introspector.get_trigger_info("update_user_timestamp")

        assert trigger is not None
        # Timing may be extracted from definition or metadata
        if trigger.timing:
            assert trigger.timing.upper() in ("BEFORE", "AFTER", "INSTEAD OF")
        else:
            # Verify timing is in definition
            assert trigger.definition is not None
            assert "BEFORE" in trigger.definition.upper()

    def test_trigger_events(self, backend_with_trigger):
        """Test trigger events detection."""
        trigger = backend_with_trigger.introspector.get_trigger_info("update_user_timestamp")

        assert trigger is not None
        # Events may be extracted from definition or metadata
        if trigger.events:
            assert "UPDATE" in [e.upper() for e in trigger.events]
        else:
            # Verify event is in definition
            assert trigger.definition is not None
            assert "UPDATE" in trigger.definition.upper()

    def test_before_insert_trigger(self, backend_with_trigger):
        """Test BEFORE INSERT trigger."""
        backend_with_trigger.executescript("""
            CREATE TRIGGER validate_before_insert
            BEFORE INSERT ON users
            FOR EACH ROW
            BEGIN
                IF NEW.name = '' THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Name cannot be empty';
                END IF;
            END;
        """)

        trigger = backend_with_trigger.introspector.get_trigger_info("validate_before_insert")

        assert trigger is not None
        assert trigger.definition is not None
        assert trigger.timing == "BEFORE"
        assert "INSERT" in trigger.events

        backend_with_trigger.executescript("DROP TRIGGER IF EXISTS validate_before_insert;")

    def test_after_delete_trigger(self, backend_with_trigger):
        """Test AFTER DELETE trigger."""
        backend_with_trigger.executescript("""
            CREATE TABLE audit_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                action VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TRIGGER after_delete_audit
            AFTER DELETE ON users
            FOR EACH ROW
            INSERT INTO audit_log (action) VALUES ('DELETE');
        """)

        trigger = backend_with_trigger.introspector.get_trigger_info("after_delete_audit")

        assert trigger is not None
        assert trigger.definition is not None
        assert trigger.timing == "AFTER"
        assert "DELETE" in trigger.events

        backend_with_trigger.executescript("""
            DROP TRIGGER IF EXISTS after_delete_audit;
            DROP TABLE IF EXISTS audit_log;
        """)


class TestAsyncTriggerIntrospection:
    """Async tests for trigger introspection."""

    @pytest.mark.asyncio
    async def test_async_list_triggers(self, async_backend_with_trigger):
        """Test async list_triggers returns TriggerInfo objects."""
        triggers = await async_backend_with_trigger.introspector.list_triggers()

        trigger_names = [t.name for t in triggers]
        assert "update_user_timestamp" in trigger_names

    @pytest.mark.asyncio
    async def test_async_get_trigger_info(self, async_backend_with_trigger):
        """Test async get_trigger_info for existing trigger."""
        trigger = await async_backend_with_trigger.introspector.get_trigger_info("update_user_timestamp")

        assert trigger is not None
        assert isinstance(trigger, TriggerInfo)
        assert trigger.name == "update_user_timestamp"

    @pytest.mark.asyncio
    async def test_async_list_triggers_caching(self, async_backend_with_trigger):
        """Test that async trigger list is cached."""
        triggers1 = await async_backend_with_trigger.introspector.list_triggers()
        triggers2 = await async_backend_with_trigger.introspector.list_triggers()

        # Should return the same cached list
        assert triggers1 is triggers2
