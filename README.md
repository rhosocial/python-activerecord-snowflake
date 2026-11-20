<!-- README.md -->
# rhosocial-activerecord-snowflake ($\rho_{\mathbf{AR}\text{-snowflake}}$)

[![Python](https://img.shields.io/pypi/pyversions/rhosocial-activerecord-snowflake.svg)](https://pypi.org/project/rhosocial-activerecord-snowflake/)
[![Apache 2.0 License](https://img.shields.io/github/license/rhosocial/python-activerecord-snowflake.svg)](https://github.com/rhosocial/python-activerecord-snowflake/blob/main/LICENSE)
[![Snowflake](https://img.shields.io/badge/Snowflake-cloud-blue?logo=snowflake)](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/README.md)

<div align="center">
    <img src="https://raw.githubusercontent.com/rhosocial/python-activerecord/main/docs/images/logo.svg" alt="rhosocial ActiveRecord Logo" width="200"/>
    <h3>Snowflake Backend for rhosocial-activerecord</h3>
    <p><b>VARIANT &amp; ARRAY · Time travel · MERGE upsert</b></p>
</div>

A [Snowflake](https://www.snowflake.com/) cloud data warehouse backend for
[rhosocial-activerecord](https://github.com/rhosocial/python-activerecord).
It cannot be used standalone.

**Keywords:** orm, activerecord, pydantic, snowflake, cloud-data-warehouse, variant, time-travel, merge

## Why This Project?

### 1. ActiveRecord semantics on a cloud warehouse

A class represents a table; an instance represents a row — with no Session object to manage. This backend binds that model to Snowflake's
three-level `database.schema.table` namespace, warehouse-based compute, and pyformat (`%s`) placeholders instead of treating the warehouse as a local database.

### 2. Snowflake-native data and operations

`VARIANT` / `ARRAY` columns, point-in-time reads via time travel (`AT(TIMESTAMP => ...)` / `BEFORE(...)`), and conditional upserts via `MERGE` are
supported by the dialect and type adapters, so you can work with them without leaving the ActiveRecord model.

## Quick Start

### Installation

```bash
pip install rhosocial-activerecord-snowflake
```

Requires Python 3.8+ on a standard GIL build, `rhosocial-activerecord>=1.0.0.dev30,<2.0.0`, and
`snowflake-connector-python>=3.0.0`. Free-threaded 3.13t is unsupported (`cffi` has no such build),
and 3.15 has no driver wheel yet.

### Configuration and first query

Snowflake is a hosted service: you need an account, a virtual warehouse, and credentials. This example declares the model, creates its table, and
runs a typed query.

```python
"""Save as demo.py and run with a live Snowflake account."""
import uuid
from typing import Annotated, ClassVar

from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig
from rhosocial.activerecord.backend.impl.snowflake.expression import SnowflakeVarcharType
from rhosocial.activerecord.base import FieldProxy, UseSqlType
from rhosocial.activerecord.model import ActiveRecord


class User(ActiveRecord):
    # Snowflake has no sequences: supply a primary key yourself (or use a DEFAULT).
    id: Annotated[str, UseSqlType(SnowflakeVarcharType(length=36))]
    name: Annotated[str, UseSqlType(SnowflakeVarcharType(length=100))]
    email: Annotated[str, UseSqlType(SnowflakeVarcharType(length=255))]
    age: int = 0

    c: ClassVar[FieldProxy] = FieldProxy()  # enables User.c.<field> expressions

    @classmethod
    def table_name(cls) -> str:
        return "users"

    @classmethod
    def primary_key(cls) -> str:
        return "id"


User.configure(
    SnowflakeConnectionConfig(
        account="your-account",
        warehouse="COMPUTE_WH",
        database="myapp",
        schema="PUBLIC",
        username="user",
        password="password",
        role="SYSADMIN",
    ),
    SnowflakeBackend,
)
User.create_table()

alice = User(id=str(uuid.uuid4()), name="Alice", email="alice@example.com", age=30)
alice.save()

adults = User.query().where(User.c.age >= 18).all()
print([user.name for user in adults])

# Inspect generated SQL without executing it (Snowflake placeholders are %s)
sql, params = User.query().where(User.c.age >= 18).to_sql()
print(sql, params)
```

> **Async is experimental — do not use in production.** `snowflake-connector-python` has no native async
> driver: `AsyncSnowflakeBackend` is a thread-pool wrapper (`asyncio.run_in_executor`) over synchronous
> calls, with no performance benefit. Use `SnowflakeBackend` in production.

## Project Architecture

```
Your Code
   ↓
Interface        models, field proxies, mixins, query builders
   ↓
ActiveRecord     lifecycle, persistence, relations
   ↓
Expressions      backend-agnostic declarations → generic statements
   ↓
Dialect          binds expressions to Snowflake SQL and `%s` placeholders
   ↓
Driver           snowflake-connector-python → Snowflake warehouse
```

For the full picture, start with the [Core Documentation](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/README.md).

**Snowflake highlights.** `SnowflakeDialect` handles the three-level namespace and identifier quoting;
`VARIANT` / `ARRAY` values are handled by registered type adapters; time-travel reads use `AT(...)` /
`BEFORE(...)` clauses; conditional upserts use `MERGE`, since Snowflake has no DML-level `RETURNING`.

## Backend Support & Progress

Snowflake is a hosted cloud service, so there is no server version to track or gate features on. This
backend ships as a separate package layered on the core `rhosocial-activerecord` library; the core library
and its docs describe ActiveRecord itself, while database-specific backends are documented in their own
repositories.

> **⚠️ Development Stage:** This project is under active development. APIs may change, and some features —
> notably the thread-pool async backend — are not yet production-ready.

## Contributing, License, Links

### Contributing

We welcome contributions! Please see [CONTRIBUTING.md](https://github.com/rhosocial/python-activerecord/blob/main/CONTRIBUTING.md) for guidelines.

### License

[Apache License 2.0](LICENSE) — Copyright © 2026 [vistart](https://github.com/vistart)

### Documentation & Links

* **[Core documentation](https://github.com/rhosocial/python-activerecord/blob/main/docs/en_US/README.md)** — full documentation table of contents
* **[Backend notes](.claude/snowflake_backend.md)** — capabilities, dialect behavior, and cloud-specific details
* **[Testing notes](.claude/testing.md)** — local and CI test setup
* **[Introspection](docs/introspection.md)** — what this backend answers and what it declines
* **[Datetime handling](docs/datetime.md)**
* **[Core library docs](https://github.com/rhosocial/python-activerecord/tree/main/docs)**

---

<div align="center">
    <p><b>Built with ❤️ by the rhosocial team</b></p>
    <p><a href="https://github.com/rhosocial/python-activerecord-snowflake">GitHub</a> · <a href="https://pypi.org/project/rhosocial-activerecord-snowflake/">PyPI</a></p>
</div>
