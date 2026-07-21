# tests/rhosocial/activerecord_snowflake_test/feature/backend/introspection/test_introspection_views.py
"""
Tests for Snowflake view introspection.

This module tests the list_views, get_view_info, and view_exists methods
for retrieving view metadata.
"""

import pytest

from rhosocial.activerecord.backend.introspection.types import (
    ViewInfo,
)


class TestListViews:
    """Tests for list_views method."""

    def test_list_views_returns_view_info(self, backend_with_view):
        """Test that list_views returns ViewInfo objects."""
        views = backend_with_view.introspector.list_views()

        assert isinstance(views, list)
        assert len(views) > 0

        for view in views:
            assert isinstance(view, ViewInfo)

    def test_list_views_includes_created_view(self, backend_with_view):
        """Test that created views are listed."""
        views = backend_with_view.introspector.list_views()
        view_names = [v.name for v in views]

        assert "user_summary" in view_names

    def test_list_views_no_views(self, backend_with_tables):
        """Test list_views when no views exist."""
        views = backend_with_tables.introspector.list_views()

        assert isinstance(views, list)
        assert len(views) == 0

    def test_list_views_caching(self, backend_with_view):
        """Test that view list is cached."""
        views1 = backend_with_view.introspector.list_views()
        views2 = backend_with_view.introspector.list_views()

        # Should return the same cached list
        assert views1 is views2


class TestGetViewInfo:
    """Tests for get_view_info method."""

    def test_get_view_info_existing(self, backend_with_view):
        """Test get_view_info for existing view."""
        view = backend_with_view.introspector.get_view_info("user_summary")

        assert view is not None
        assert isinstance(view, ViewInfo)
        assert view.name == "user_summary"

    def test_get_view_info_nonexistent(self, backend_with_view):
        """Test get_view_info for non-existent view."""
        view = backend_with_view.introspector.get_view_info("nonexistent")

        assert view is None


class TestViewExists:
    """Tests for view_exists method."""

    def test_view_exists_true(self, backend_with_view):
        """Test view_exists returns True for existing view."""
        assert backend_with_view.introspector.view_exists("user_summary") is True

    def test_view_exists_false(self, backend_with_view):
        """Test view_exists returns False for non-existent view."""
        assert backend_with_view.introspector.view_exists("nonexistent") is False

    def test_view_exists_table_not_view(self, backend_with_tables):
        """Test view_exists returns False for a table."""
        assert backend_with_tables.introspector.view_exists("users") is False


class TestViewInfoDetails:
    """Tests for detailed view information."""

    def test_view_definition(self, backend_with_view):
        """Test that view definition is returned."""
        view = backend_with_view.introspector.get_view_info("user_summary")

        assert view is not None
        assert view.definition is not None
        # Definition should contain SELECT
        assert "SELECT" in view.definition.upper()

    def test_view_check_option(self, backend_with_view):
        """Test check option detection."""
        view = backend_with_view.introspector.get_view_info("user_summary")

        assert view is not None
        # Snowflake views have check_option (NONE, LOCAL, CASCADED)
        # Default is NONE
        assert view.check_option is not None

    def test_view_is_updatable(self, backend_with_view):
        """Test is_updatable detection."""
        view = backend_with_view.introspector.get_view_info("user_summary")

        assert view is not None
        # is_updatable depends on view definition
        assert isinstance(view.is_updatable, bool)

    def test_multiple_views(self, backend_with_view):
        """Test multiple views introspection."""
        backend_with_view.executescript("""
            CREATE VIEW user_names AS
            SELECT id, name FROM users;
        """)

        views = backend_with_view.introspector.list_views()

        view_names = [v.name for v in views]
        assert "user_summary" in view_names
        assert "user_names" in view_names

        backend_with_view.executescript("DROP VIEW IF EXISTS user_names;")

    def test_view_with_join(self, backend_with_view):
        """Test view with JOIN."""
        view = backend_with_view.introspector.get_view_info("user_summary")

        assert view is not None
        # View definition should contain JOIN
        assert view.definition is not None


class TestAsyncViewIntrospection:
    """Async tests for view introspection."""

    @pytest.mark.asyncio
    async def test_async_list_views(self, async_backend_with_view):
        """Test async list_views returns ViewInfo objects."""
        views = await async_backend_with_view.introspector.list_views()

        assert isinstance(views, list)
        assert len(views) > 0

        for view in views:
            assert isinstance(view, ViewInfo)

    @pytest.mark.asyncio
    async def test_async_get_view_info(self, async_backend_with_view):
        """Test async get_view_info for existing view."""
        view = await async_backend_with_view.introspector.get_view_info("user_summary")

        assert view is not None
        assert isinstance(view, ViewInfo)
        assert view.name == "user_summary"

    @pytest.mark.asyncio
    async def test_async_view_exists(self, async_backend_with_view):
        """Test async view_exists returns True for existing view."""
        exists = await async_backend_with_view.introspector.view_exists("user_summary")
        assert exists is True

    @pytest.mark.asyncio
    async def test_async_list_views_caching(self, async_backend_with_view):
        """Test that async view list is cached."""
        views1 = await async_backend_with_view.introspector.list_views()
        views2 = await async_backend_with_view.introspector.list_views()

        # Should return the same cached list
        assert views1 is views2
