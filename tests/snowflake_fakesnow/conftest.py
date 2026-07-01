"""fakesnow integration test fixtures (Layer 3).

Connects SnowflakeBackend to fakesnow (DuckDB emulator) for
integration tests that don't require a real Snowflake account.

fakesnow replaces snowflake.connector.connect at import time,
so SnowflakeBackend can be used normally without any code changes.
"""
import pytest
import fakesnow as _fakesnow

from rhosocial.activerecord.backend.impl.snowflake import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig

# fakesnow patterns that should be treated as no-ops
FAKESNOW_NOP_PATTERNS = [
    r"CREATE\s+(?:OR\s+REPLACE\s+)?STREAM\s+.*",
    r"CREATE\s+(?:OR\s+REPLACE\s+)?TASK\s+.*",
    r"CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+.*",
    r"ALTER\s+TABLE\s+.*\s+CLUSTER\s+BY\s+.*",
]


@pytest.fixture
def _fakesnow_patch():
    """Per-test fakesnow patch (function scope).

    Detects if a fakesnow patch is already active (e.g. from
    tests/providers/scenarios.py) and skips re-patching to avoid
    conflicts (fakesnow.patch is not re-entrant).
    """
    if _is_fakesnow_already_patched():
        yield
    else:
        with _fakesnow.patch(nop_regexes=FAKESNOW_NOP_PATTERNS):
            yield


@pytest.fixture(scope="session")
def _fakesnow_session_patch():
    """Session-scoped fakesnow patch."""
    if _is_fakesnow_already_patched():
        yield
    else:
        with _fakesnow.patch(nop_regexes=FAKESNOW_NOP_PATTERNS):
            yield


def _is_fakesnow_already_patched():
    """Check if fakesnow has already patched snowflake.connector."""
    try:
        import snowflake.connector
        # fakesnow replaces snowflake.connector.connect with FakeSnowflakeFlakeConnection
        return hasattr(snowflake.connector, 'connect') and \
               snowflake.connector.connect.__module__ != 'snowflake.connector'
    except ImportError:
        return False


@pytest.fixture
def snowflake_config():
    """Standard test config (fakesnow ignores account/password validation)."""
    return SnowflakeConnectionConfig(
        account="test-account.us-east-1",
        user="test_user",
        password="test_password",
        database="TEST_DB",
        schema="PUBLIC",
        warehouse="TEST_WH",
        role="SYSADMIN",
    )


@pytest.fixture
def fs_backend(snowflake_config, _fakesnow_patch):
    """Per-test SnowflakeBackend connected to fakesnow (DuckDB).

    Creates a fresh database and schema for each test function.
    """
    backend = SnowflakeBackend(connection_config=snowflake_config)
    backend.connect()
    yield backend
    backend.disconnect()


@pytest.fixture(scope="session")
def fs_backend_session(snowflake_config, _fakesnow_session_patch):
    """Session-scoped SnowflakeBackend for read-only or stable-schema tests.

    Faster than fs_backend, but tests share data.
    """
    backend = SnowflakeBackend(connection_config=snowflake_config)
    backend.connect()
    yield backend
    backend.disconnect()


# Type mapping for auto-generated DDL in tests
_TYPE_MAP = {
    "int": "INTEGER",
    "str": "VARCHAR(16777216)",
    "float": "FLOAT",
    "bool": "BOOLEAN",
    "datetime": "TIMESTAMP_NTZ",
    "UUID": "VARCHAR(36)",
    "dict": "VARIANT",
    "list": "ARRAY",
    "Decimal": "NUMBER(38, 10)",
    "NoneType": "VARCHAR(16777216)",
}


def _generate_ddl(model_class) -> str:
    """Generate basic Snowflake DDL from Pydantic model fields."""
    fields = []
    pk_field = model_class.primary_key() if hasattr(model_class, "primary_key") else "id"

    for field_name, field_info in model_class.model_fields.items():
        annotation = field_info.annotation
        type_name = getattr(annotation, "__name__", str(annotation)).split(".")[-1]
        if hasattr(annotation, "__args__"):
            inner = [a for a in annotation.__args__ if a is not type(None)]
            if inner:
                type_name = getattr(inner[0], "__name__", str(inner[0])).split(".")[-1]

        sf_type = _TYPE_MAP.get(type_name, "VARCHAR(16777216)")
        col_name = field_name.upper()

        if field_name == pk_field:
            fields.append(f'"{col_name}" {sf_type} PRIMARY KEY')
        elif field_info.is_required():
            fields.append(f'"{col_name}" {sf_type} NOT NULL')
        else:
            fields.append(f'"{col_name}" {sf_type}')

    table = model_class.table_name().upper()
    return f'CREATE TABLE IF NOT EXISTS {table} (\n  ' + ',\n  '.join(fields) + '\n)'


@pytest.fixture
def fs_model(fs_backend):
    """Helper to bind an ActiveRecord model to fs_backend and create its table.

    Usage:
        MyModel = fs_model(MyModel, "CREATE TABLE ...")
        MyModel = fs_model(MyModel)  # auto-generate DDL
    """
    registered = []

    def _register(model_class, ddl: str = None):
        from rhosocial.activerecord.backend.impl.snowflake import SnowflakeBackend as SB
        model_class.configure(fs_backend.config, SB)
        create_ddl = ddl or _generate_ddl(model_class)
        if create_ddl:
            fs_backend.execute(create_ddl, ())
        registered.append(model_class)
        return model_class

    yield _register

    for model_class in registered:
        table = model_class.table_name().upper()
        try:
            fs_backend.execute(f"DROP TABLE IF EXISTS {table}", ())
        except Exception:
            pass
