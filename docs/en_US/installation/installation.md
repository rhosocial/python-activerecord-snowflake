# Installation guide

## Requirements

| Item | Requirement |
|------|-------------|
| Python | 3.8 – 3.14, standard GIL build |
| Core library | `rhosocial-activerecord>=1.0.0.dev30,<2.0.0` |
| Driver | `snowflake-connector-python>=3.0.0` |
| Snowflake | A hosted account, a virtual warehouse, and credentials |

Free-threaded Python 3.13t is **not supported** (`cffi` has no free-threaded
build); 3.14t is experimental and 3.15 has no driver wheel yet. See
[Overview](../introduction/overview.md).

## Install

```bash
pip install rhosocial-activerecord-snowflake
```

The two runtime dependencies are installed automatically. There is nothing to
install on the Snowflake side — the warehouse is a hosted service, so no local
server binary or port configuration is involved.

## Optional extras

```bash
# Test tooling
pip install "rhosocial-activerecord-snowflake[test]"

# Formatters, linters and type checker
pip install "rhosocial-activerecord-snowflake[dev]"

# Documentation toolchain
pip install "rhosocial-activerecord-snowflake[docs]"
```

> When developing against local source trees, install the core library and the
> test suite from their local paths explicitly rather than relying on the
> bare package names declared in the extras. See [Test configuration](../testing/README.md).

## Verify the install

```python
from rhosocial.activerecord.backend.impl.snowflake.backend import SnowflakeBackend
from rhosocial.activerecord.backend.impl.snowflake.config import SnowflakeConnectionConfig

print(SnowflakeBackend, SnowflakeConnectionConfig)
```

This import needs no network access. A real connection additionally needs an
account, warehouse and credentials — see [Connection configuration](configuration.md).

## Next steps

- [Connection configuration](configuration.md)
- [Three-part naming & identifiers](../features/naming.md)
