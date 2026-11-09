# tests/providers/relation.py
"""Relation test provider for the Snowflake backend.

Implements ``IRelationSyncProvider`` and ``IRelationAsyncProvider`` against
fakesnow (the DuckDB-based Snowflake emulator) or a real Snowflake account.

The ordered-HasMany contract only needs the User/Post/Comment models, but the
provider implements the whole relation interface so the relation feature
directory has one coherent setup and cleanup path.
"""
from typing import Dict, List, Tuple, Type

from rhosocial.activerecord.backend.impl.snowflake.backend.async_backend import (
    AsyncSnowflakeBackend,
)
from rhosocial.activerecord.model import ActiveRecord, AsyncActiveRecord
from rhosocial.activerecord.testsuite.feature.relation.fixtures.models import (
    Author,
    AsyncBoundaryOwner,
    AsyncBoundaryPost,
    AsyncBoundaryProfile,
    AsyncComment,
    AsyncPost,
    AsyncUser,
    Book,
    BoundaryOwner,
    BoundaryPost,
    BoundaryProfile,
    Chapter,
    Comment,
    Department,
    Employee,
    Post,
    Profile,
    User,
)
from rhosocial.activerecord.testsuite.feature.relation.interfaces import (
    IRelationAsyncProvider,
    IRelationSyncProvider,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

from .scenarios import get_enabled_scenarios, get_scenario


USER_POST_COMMENT_SCHEMA = """
    CREATE TABLE users (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255),
        settings VARCHAR
    );
    CREATE TABLE posts (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        body VARCHAR NOT NULL,
        user_id INTEGER NOT NULL,
        view_count INTEGER NOT NULL DEFAULT 0,
        metadata VARCHAR
    );
    CREATE TABLE comments (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        body VARCHAR NOT NULL,
        post_id INTEGER NOT NULL,
        meta VARCHAR
    );
"""

EMPLOYEE_DEPARTMENT_SCHEMA = """
    CREATE TABLE departments (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description VARCHAR
    );
    CREATE TABLE employees (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL,
        department_id INTEGER NOT NULL
    );
"""

AUTHOR_BOOK_SCHEMA = """
    CREATE TABLE authors (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL
    );
    CREATE TABLE books (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        author_id INTEGER NOT NULL
    );
    CREATE TABLE chapters (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        book_id INTEGER NOT NULL
    );
    CREATE TABLE profiles (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        bio VARCHAR NOT NULL,
        author_id INTEGER NOT NULL
    );
"""

RELATION_BOUNDARY_SCHEMA = """
    CREATE TABLE relation_boundary_owners (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL
    );
    CREATE TABLE relation_boundary_profiles (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        bio VARCHAR NOT NULL,
        owner_id INTEGER
    );
    CREATE TABLE relation_boundary_posts (
        id INTEGER AUTOINCREMENT PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        owner_id INTEGER
    );
"""


def _statements(sql: str) -> List[str]:
    """Split one schema script into executable statements."""
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def _ddl_options() -> ExecutionOptions:
    return ExecutionOptions(stmt_type=StatementType.DDL)


class RelationProviderBase:
    """Shared, non-I/O helpers for the sync and async relation providers."""

    def __init__(self) -> None:
        self._created_tables: List[str] = []

    def get_test_scenarios(self) -> List[str]:
        return list(get_enabled_scenarios().keys())

    def _remember_tables(self, *table_names: str) -> None:
        for table_name in table_names:
            if table_name not in self._created_tables:
                self._created_tables.append(table_name)

    def _load_relation_boundary_dataset(
        self,
        owner_class,
        profile_class,
        post_class,
        dataset_name: str,
    ) -> Dict[str, int]:
        if dataset_name == "null_foreign_key":
            profile = profile_class(bio="No owner", owner_id=None)
            profile.save()
            return {"profile_id": profile.id}

        if dataset_name == "orphan_foreign_key":
            missing_owner_id = 999999
            post = post_class(title="Orphan post", owner_id=missing_owner_id)
            post.save()
            return {"post_id": post.id, "missing_owner_id": missing_owner_id}

        if dataset_name == "owner_without_children":
            owner = owner_class(name="Owner without children")
            owner.save()
            return {"owner_id": owner.id}

        if dataset_name == "multiple_has_one_matches":
            owner = owner_class(name="Owner with duplicate profiles")
            owner.save()
            first = profile_class(bio="First profile", owner_id=owner.id)
            first.save()
            second = profile_class(bio="Second profile", owner_id=owner.id)
            second.save()
            return {
                "owner_id": owner.id,
                "first_profile_id": first.id,
                "second_profile_id": second.id,
            }

        raise ValueError("Unknown relation boundary dataset: %s" % dataset_name)


class RelationSyncProvider(RelationProviderBase, IRelationSyncProvider):
    """Synchronous Snowflake implementation of the relation test provider."""

    def __init__(self) -> None:
        super().__init__()
        self._active_backends: List = []
        self._user_post_comment_setup = False
        self._relation_boundary_setup = False

    def _configure(self, model_class, config, backend_class, backend):
        model_class.__connection_config__ = config
        model_class.__backend_class__ = backend_class
        model_class.__backend__ = backend

    def _create_schema(self, backend, schema_sql: str, *tables: str) -> None:
        for statement in _statements(schema_sql):
            backend.execute(statement, (), options=_ddl_options())
        self._remember_tables(*tables)

    def _setup_employee_department(self, scenario_name: str):
        backend_class, config = get_scenario(scenario_name)
        Employee.configure(config, backend_class)
        backend = Employee.backend()
        backend.connect()
        self._active_backends.append(backend)
        self._create_schema(
            backend,
            EMPLOYEE_DEPARTMENT_SCHEMA,
            "departments",
            "employees",
        )
        self._configure(Department, config, backend_class, backend)
        return Employee, Department

    def _setup_author_book(self, scenario_name: str):
        backend_class, config = get_scenario(scenario_name)
        Author.configure(config, backend_class)
        backend = Author.backend()
        backend.connect()
        self._active_backends.append(backend)
        self._create_schema(
            backend,
            AUTHOR_BOOK_SCHEMA,
            "authors",
            "books",
            "chapters",
            "profiles",
        )
        for model_class in (Book, Chapter, Profile):
            self._configure(model_class, config, backend_class, backend)
        return Author, Book, Chapter, Profile

    def _setup_user_post_comment(self, scenario_name: str) -> None:
        if self._user_post_comment_setup:
            return
        backend_class, config = get_scenario(scenario_name)
        User.configure(config, backend_class)
        backend = User.backend()
        backend.connect()
        self._active_backends.append(backend)
        self._create_schema(
            backend,
            USER_POST_COMMENT_SCHEMA,
            "comments",
            "posts",
            "users",
        )
        for model_class in (Post, Comment):
            self._configure(model_class, config, backend_class, backend)
        self._user_post_comment_setup = True

    def _setup_relation_boundary(self, scenario_name: str) -> None:
        if self._relation_boundary_setup:
            return
        backend_class, config = get_scenario(scenario_name)
        BoundaryOwner.configure(config, backend_class)
        backend = BoundaryOwner.backend()
        backend.connect()
        self._active_backends.append(backend)
        self._create_schema(
            backend,
            RELATION_BOUNDARY_SCHEMA,
            "relation_boundary_owners",
            "relation_boundary_profiles",
            "relation_boundary_posts",
        )
        for model_class in (BoundaryProfile, BoundaryPost):
            self._configure(model_class, config, backend_class, backend)
        self._relation_boundary_setup = True

    def setup_employee_department_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord]]:
        return self._setup_employee_department(scenario_name)

    def setup_author_book_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[
        Type[ActiveRecord],
        Type[ActiveRecord],
        Type[ActiveRecord],
        Type[ActiveRecord],
    ]:
        return self._setup_author_book(scenario_name)

    def setup_user_model(self, scenario_name: str) -> Type[ActiveRecord]:
        self._setup_user_post_comment(scenario_name)
        return User

    def setup_post_model(self, scenario_name: str) -> Type[ActiveRecord]:
        self._setup_user_post_comment(scenario_name)
        return Post

    def setup_comment_model(self, scenario_name: str) -> Type[ActiveRecord]:
        self._setup_user_post_comment(scenario_name)
        return Comment

    def setup_relation_boundary_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[Type[ActiveRecord], Type[ActiveRecord], Type[ActiveRecord]]:
        self._setup_relation_boundary(scenario_name)
        return BoundaryOwner, BoundaryProfile, BoundaryPost

    def load_relation_boundary_dataset(
        self,
        scenario_name: str,
        dataset_name: str,
    ) -> Dict[str, int]:
        self._setup_relation_boundary(scenario_name)
        return self._load_relation_boundary_dataset(
            BoundaryOwner,
            BoundaryProfile,
            BoundaryPost,
            dataset_name,
        )

    def cleanup_after_test(self, scenario_name: str) -> None:
        for backend in self._active_backends:
            try:
                for table_name in reversed(self._created_tables):
                    try:
                        backend.execute(
                            "DROP TABLE IF EXISTS %s" % table_name,
                            (),
                            options=_ddl_options(),
                        )
                    except Exception:
                        pass
            finally:
                try:
                    backend.disconnect()
                except Exception:
                    pass
        self._active_backends.clear()
        self._created_tables.clear()


class RelationAsyncProvider(RelationProviderBase, IRelationAsyncProvider):
    """Asynchronous Snowflake implementation of the relation test provider."""

    def __init__(self) -> None:
        super().__init__()
        self._active_async_backends: List = []
        self._user_post_comment_setup = False
        self._relation_boundary_setup = False

    def _configure(self, model_class, config, backend_class, backend):
        model_class.__connection_config__ = config
        model_class.__backend_class__ = backend_class
        model_class.__backend__ = backend

    async def _create_schema(self, backend, schema_sql: str, *tables: str) -> None:
        for statement in _statements(schema_sql):
            await backend.execute(statement, (), options=_ddl_options())
        self._remember_tables(*tables)

    async def _setup_employee_department(self, scenario_name: str):
        _, config = get_scenario(scenario_name)
        await Employee.configure(config, AsyncSnowflakeBackend)
        backend = Employee.backend()
        await backend.connect()
        self._active_async_backends.append(backend)
        await self._create_schema(
            backend,
            EMPLOYEE_DEPARTMENT_SCHEMA,
            "departments",
            "employees",
        )
        self._configure(Department, config, AsyncSnowflakeBackend, backend)
        return Employee, Department

    async def _setup_author_book(self, scenario_name: str):
        _, config = get_scenario(scenario_name)
        await Author.configure(config, AsyncSnowflakeBackend)
        backend = Author.backend()
        await backend.connect()
        self._active_async_backends.append(backend)
        await self._create_schema(
            backend,
            AUTHOR_BOOK_SCHEMA,
            "authors",
            "books",
            "chapters",
            "profiles",
        )
        for model_class in (Book, Chapter, Profile):
            self._configure(model_class, config, AsyncSnowflakeBackend, backend)
        return Author, Book, Chapter, Profile

    async def _setup_user_post_comment(self, scenario_name: str) -> None:
        if self._user_post_comment_setup:
            return
        _, config = get_scenario(scenario_name)
        await AsyncUser.configure(config, AsyncSnowflakeBackend)
        backend = AsyncUser.backend()
        await backend.connect()
        self._active_async_backends.append(backend)
        await self._create_schema(
            backend,
            USER_POST_COMMENT_SCHEMA,
            "comments",
            "posts",
            "users",
        )
        for model_class in (AsyncPost, AsyncComment):
            self._configure(model_class, config, AsyncSnowflakeBackend, backend)
        self._user_post_comment_setup = True

    async def _setup_relation_boundary(self, scenario_name: str) -> None:
        if self._relation_boundary_setup:
            return
        _, config = get_scenario(scenario_name)
        await AsyncBoundaryOwner.configure(config, AsyncSnowflakeBackend)
        backend = AsyncBoundaryOwner.backend()
        await backend.connect()
        self._active_async_backends.append(backend)
        await self._create_schema(
            backend,
            RELATION_BOUNDARY_SCHEMA,
            "relation_boundary_owners",
            "relation_boundary_profiles",
            "relation_boundary_posts",
        )
        for model_class in (AsyncBoundaryProfile, AsyncBoundaryPost):
            self._configure(model_class, config, AsyncSnowflakeBackend, backend)
        self._relation_boundary_setup = True

    async def setup_employee_department_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[Type[AsyncActiveRecord], Type[AsyncActiveRecord]]:
        return await self._setup_employee_department(scenario_name)

    async def setup_author_book_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[
        Type[AsyncActiveRecord],
        Type[AsyncActiveRecord],
        Type[AsyncActiveRecord],
        Type[AsyncActiveRecord],
    ]:
        return await self._setup_author_book(scenario_name)

    async def setup_user_model(self, scenario_name: str) -> Type[AsyncActiveRecord]:
        await self._setup_user_post_comment(scenario_name)
        return AsyncUser

    async def setup_post_model(self, scenario_name: str) -> Type[AsyncActiveRecord]:
        await self._setup_user_post_comment(scenario_name)
        return AsyncPost

    async def setup_comment_model(self, scenario_name: str) -> Type[AsyncActiveRecord]:
        await self._setup_user_post_comment(scenario_name)
        return AsyncComment

    async def setup_relation_boundary_fixtures(
        self,
        scenario_name: str,
    ) -> Tuple[
        Type[AsyncActiveRecord],
        Type[AsyncActiveRecord],
        Type[AsyncActiveRecord],
    ]:
        await self._setup_relation_boundary(scenario_name)
        return AsyncBoundaryOwner, AsyncBoundaryProfile, AsyncBoundaryPost

    async def load_relation_boundary_dataset(
        self,
        scenario_name: str,
        dataset_name: str,
    ) -> Dict[str, int]:
        await self._setup_relation_boundary(scenario_name)
        return await self._load_relation_boundary_dataset_async(
            AsyncBoundaryOwner,
            AsyncBoundaryProfile,
            AsyncBoundaryPost,
            dataset_name,
        )

    async def _load_relation_boundary_dataset_async(
        self,
        owner_class,
        profile_class,
        post_class,
        dataset_name: str,
    ) -> Dict[str, int]:
        if dataset_name == "null_foreign_key":
            profile = profile_class(bio="No owner", owner_id=None)
            await profile.save()
            return {"profile_id": profile.id}

        if dataset_name == "orphan_foreign_key":
            missing_owner_id = 999999
            post = post_class(title="Orphan post", owner_id=missing_owner_id)
            await post.save()
            return {"post_id": post.id, "missing_owner_id": missing_owner_id}

        if dataset_name == "owner_without_children":
            owner = owner_class(name="Owner without children")
            await owner.save()
            return {"owner_id": owner.id}

        if dataset_name == "multiple_has_one_matches":
            owner = owner_class(name="Owner with duplicate profiles")
            await owner.save()
            first = profile_class(bio="First profile", owner_id=owner.id)
            await first.save()
            second = profile_class(bio="Second profile", owner_id=owner.id)
            await second.save()
            return {
                "owner_id": owner.id,
                "first_profile_id": first.id,
                "second_profile_id": second.id,
            }

        raise ValueError("Unknown relation boundary dataset: %s" % dataset_name)

    async def cleanup_after_test(self, scenario_name: str) -> None:
        for backend in self._active_async_backends:
            try:
                for table_name in reversed(self._created_tables):
                    try:
                        await backend.execute(
                            "DROP TABLE IF EXISTS %s" % table_name,
                            (),
                            options=_ddl_options(),
                        )
                    except Exception:
                        pass
            finally:
                try:
                    await backend.disconnect()
                except Exception:
                    pass
        self._active_async_backends.clear()
        self._created_tables.clear()
