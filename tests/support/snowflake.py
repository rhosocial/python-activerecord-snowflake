# tests/support/snowflake.py
"""The Snowflake backend's test scenarios.

The scenario file holds account-level connection parameters only; the logical
database name comes from the test directory and is injected here.  Snowflake is
a server backend, so a scenario maps to one account, and every test directory
owns one database on that account.

Two shapes are supported, and they are mutually exclusive:

* a real account, configured either by the scenario file or by the
  ``SNOWFLAKE_ACCOUNT``/``SNOWFLAKE_USER``/... environment variables;
* the ``fakesnow`` emulator (DuckDB), which is enabled only when the package is
  installed and no real account is configured.  Emulating and really
  connecting cannot share one process, because the emulator works by
  monkey-patching ``snowflake.connector``.
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from rhosocial.activerecord.backend.impl.snowflake.backend import (
    AsyncSnowflakeBackend,
    SnowflakeBackend,
)
from rhosocial.activerecord.backend.impl.snowflake.config import (
    SnowflakeConnectionConfig,
)
from rhosocial.activerecord.backend.options import ExecutionOptions
from rhosocial.activerecord.backend.schema import StatementType

CONFIG_PATH = Path(
    os.environ.get("SNOWFLAKE_SCENARIOS_CONFIG_PATH")
    or Path(__file__).resolve().parents[1] / "config" / "snowflake_scenarios.yaml"
)

# The scenario file describes an account, never a database or schema: both are
# derived (the database from the test directory, the schema from Snowflake's
# own default).  ``enabled`` is a scenario toggle, not a connection parameter.
SERVER_ONLY_KEYS = ("database", "schema", "enabled")

# The database every Snowflake account ships with.  Maintenance work (dropping
# and creating databases) does not need it -- a session with no current
# database can create one -- but dialect probes do need a database that exists
# before any test database has been created.
MAINTENANCE_DATABASE = "SNOWFLAKE"

# The emulator scenario's name.  Only this name is treated as "run against
# fakesnow"; a file that defines its own scenarios is left alone.
EMULATOR_SCENARIO = "fakesnow"

# The emulator connects to DuckDB underneath.  A DuckDB database that is not
# told which schema to use has no current schema, so every ``CREATE TABLE``
# would be refused; Snowflake's own default on a real account is ``PUBLIC``,
# and naming it here keeps both shapes identical from the test's point of view.
EMULATOR_SCHEMA = "PUBLIC"

# fakesnow reports version ``(0, 0, 0)``; capability probes that gate RETURNING
# on a server version would then disable the code path CRUD tests exercise.
# Pinning a contemporary Snowflake version is the emulator's answer, not the
# backend's (the dialect still renders everything itself).
EMULATOR_VERSION = (8, 0, 0)

DDL_OPTIONS = ExecutionOptions(stmt_type=StatementType.DDL)


def _load_scenarios(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load one account-parameter dict per scenario from the YAML file.

    A missing default file means "no scenario configured", which the testsuite
    reports as skipped tests.  A path named through the environment, however,
    is a deliberate choice: if it does not exist, that is an error rather than
    an empty run.
    """
    if not path.exists():
        if os.environ.get("SNOWFLAKE_SCENARIOS_CONFIG_PATH"):
            raise FileNotFoundError(
                f"SNOWFLAKE_SCENARIOS_CONFIG_PATH names {path}, which does not exist"
            )
        return {}
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    entries = data.get("scenarios") or {}
    return {
        name: {key: value for key, value in entry.items() if key not in SERVER_ONLY_KEYS}
        for name, entry in entries.items()
    }


def _scenario_from_environment() -> Dict[str, Any]:
    """Build the ``snowflake`` scenario from the documented environment variables."""
    names = {
        "account": "SNOWFLAKE_ACCOUNT",
        "user": "SNOWFLAKE_USER",
        "password": "SNOWFLAKE_PASSWORD",
        "warehouse": "SNOWFLAKE_WAREHOUSE",
        "role": "SNOWFLAKE_ROLE",
    }
    return {
        key: os.environ[env_name] for key, env_name in names.items() if os.environ.get(env_name)
    }


_fakesnow_patch = None


def _activate_fakesnow() -> bool:
    """Enter ``fakesnow.patch()`` once, or return False when it is unavailable.

    The emulator is patched at import time because the scenario map is built
    then, and every later ``snowflake.connector.connect`` call must already be
    the fake.  Databases are file-backed under a per-process temporary
    directory: ``fakesnow`` defaults to a fresh in-memory database per
    connection, and the testsuite deliberately keeps the sync tables prepared
    on one connection while async tests open their own, so two connections
    have to see the same database to share it.
    """
    global _fakesnow_patch
    if _fakesnow_patch is not None:
        return True
    try:
        import fakesnow
    except ImportError:
        return False
    db_path = os.environ.get("FAKESNOW_DB_PATH")
    if not db_path:
        db_path = tempfile.mkdtemp(prefix="fakesnow-")
    _fakesnow_patch = fakesnow.patch(db_path=db_path)
    _fakesnow_patch.__enter__()
    return True


def _enabled_scenarios() -> Dict[str, Dict[str, Any]]:
    """Return the scenarios this run can actually use.

    Without a real account the emulator is the only option.  CI enables it by
    writing the scenario file and exporting
    ``SNOWFLAKE_SCENARIOS_CONFIG_PATH``; a developer with neither an account
    nor the emulator gets an empty map, which the testsuite reports as
    "got empty parameter set".  A placeholder account must never reach the
    real Snowflake endpoint, so the emulator scenario is dropped rather than
    left to fail on connect.
    """
    loaded = _load_scenarios(CONFIG_PATH)
    if os.environ.get("SNOWFLAKE_ACCOUNT"):
        loaded.pop(EMULATOR_SCENARIO, None)
        loaded.setdefault("snowflake", _scenario_from_environment())
        return loaded
    if EMULATOR_SCENARIO in loaded and not _activate_fakesnow():
        loaded.pop(EMULATOR_SCENARIO)
    return loaded


SCENARIO_MAP = _enabled_scenarios()
SCENARIOS = tuple(SCENARIO_MAP)


def _identifier(name: str) -> str:
    """Return the database name as Snowflake resolves it.

    Snowflake folds unquoted identifiers to upper case, and the driver passes
    the session's ``database`` through the same folding.  Leaving the name
    unquoted therefore keeps the database this call creates and the database
    the tests connect to the same object; quoting it would create a lower-case
    object the session could not find.
    """
    if not all(character.isalnum() or character == "_" for character in name):
        raise ValueError(f"Not a plain Snowflake database name: {name!r}")
    return name


@dataclass(frozen=True)
class SnowflakeScenario:
    """One Snowflake test scenario: an account plus the backend classes."""

    name: str
    server: Dict[str, Any]
    backend_class: Any = SnowflakeBackend
    async_backend_class: Any = AsyncSnowflakeBackend
    maintenance_database: Optional[str] = MAINTENANCE_DATABASE
    emulator: bool = False

    def make_config(self, database: Optional[str]) -> SnowflakeConnectionConfig:
        """Return the connection configuration for this database on this account."""
        parameters = dict(self.server)
        if database is not None:
            parameters["database"] = database
        if self.emulator:
            # DuckDB needs a current schema and a version to probe; a real
            # account supplies both itself, and naming them here would pin a
            # real deployment to the emulator's defaults.
            parameters.setdefault("schema", EMULATOR_SCHEMA)
            parameters.setdefault("version", EMULATOR_VERSION)
        return SnowflakeConnectionConfig(**parameters)

    def reset_database(self, database: str) -> None:
        """Drop and recreate ``database`` on this scenario's account.

        The maintenance session selects no database: in Snowflake an account
        level session can create and drop databases, and it avoids depending on
        any database (including the emulator's) already being there.

        The emulator cannot execute ``CREATE/DROP DATABASE`` -- its parser
        rejects them -- and creates the database when the first connection
        names it.  Skipping the reset is therefore not a leak: the directory's
        ``prepare`` / ``teardown`` own every table, and each directory connects
        to a database name only it uses.
        """
        if self.emulator:
            return
        backend = self.backend_class(connection_config=self.make_config(None))
        backend.connect()
        try:
            backend.execute(
                f"DROP DATABASE IF EXISTS {_identifier(database)}",
                (),
                options=DDL_OPTIONS,
            )
            backend.execute(
                f"CREATE DATABASE {_identifier(database)}",
                (),
                options=DDL_OPTIONS,
            )
        finally:
            backend.disconnect()


def scenario(name: str) -> SnowflakeScenario:
    """Return the scenario called ``name``."""
    try:
        server = SCENARIO_MAP[name]
    except KeyError:
        raise KeyError(f"Unknown Snowflake scenario: {name}") from None
    return SnowflakeScenario(name, dict(server), emulator=name == EMULATOR_SCENARIO)


def get_enabled_scenarios() -> Dict[str, Dict[str, Any]]:
    """Return the scenarios this backend enables, as a name -> account map."""
    return {name: dict(server) for name, server in SCENARIO_MAP.items()}


def get_scenario(name: str):
    """Return ``(backend_class, config)`` for a benchmark database."""
    current = scenario(name)
    current.reset_database("test_benchmark")
    return current.backend_class, current.make_config("test_benchmark")


def get_scenario_raw(name: str):
    """Return ``(backend_class, config)`` for an account-level connection.

    Falls back to the first configured scenario when CI enables only one.
    """
    resolved = name if name in SCENARIO_MAP else next(iter(SCENARIO_MAP), None)
    if resolved is None:
        raise KeyError(f"No {name} scenario configured")
    current = scenario(resolved)
    return current.backend_class, current.make_config(current.maintenance_database)
