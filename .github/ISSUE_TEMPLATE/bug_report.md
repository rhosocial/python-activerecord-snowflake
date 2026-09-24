---
name: Bug Report
about: Report a bug in the rhosocial ActiveRecord Snowflake backend
title: '[BUG] '
labels: 'bug'
assignees: ''
---

## Before Submitting

Please ensure this bug is specific to the Snowflake backend. For behavior shared by all database backends, please submit the bug report to the core `rhosocial-activerecord` repository instead.

## Description

A clear and concise description of the bug.

## Environment

- **rhosocial-activerecord-snowflake Version**: [e.g. 1.0.0.dev2]
- **Python Version**: [e.g. 3.14]
- **Snowflake Connector Version**: [e.g. 3.17.0]
- **Snowflake Account/Region**: [e.g. account/region]
- **Warehouse/Database/Schema**: [e.g. warehouse/database/schema]
- **OS**: [e.g. Linux, macOS, Windows]

## Steps to Reproduce

1.
2.
3.

## Expected Behavior

A clear and concise description of what you expected to happen.

## Actual Behavior

What actually happened instead of the expected behavior.

## Database Query

If applicable, provide the generated SQL query that causes the issue:

```sql
-- Your problematic SQL query here
```

## Model Definition

If the issue is related to a specific model, please share your model definition:

```python
# Example model definition
class User(ActiveRecord):
    __table_name__ = 'users'

    id: Optional[int] = None
    name: str
    email: EmailStr
```

## Error Details

If you're getting an error, include the full error message and stack trace:

```
Paste the full error message here
```

## Additional Context

Any other context about the problem here.
