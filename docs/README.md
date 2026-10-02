# rhosocial-activerecord-snowflake

Snowflake backend implementation for [rhosocial-activerecord](https://github.com/rhosocial/python-activerecord).

## Documentation / 文档

Please select your language / 请选择语言：

- [English Documentation](en_US/README.md)
- [中文文档 (Chinese)](zh_CN/README.md)

## Overview

The Snowflake backend brings the ActiveRecord pattern to Snowflake through the
`snowflake-connector-python` driver. Snowflake is the only backend in this project with
a genuine schema level nested inside a database, which makes its naming rules differ
from every other backend.

For the main ActiveRecord framework documentation, please visit the
[python-activerecord docs](https://github.com/rhosocial/python-activerecord/tree/docs/docs).