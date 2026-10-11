# src/rhosocial/activerecord/backend/impl/snowflake/protocols/type.py
"""Snowflake type family protocol.

Feature Source: Snowflake native

This dialect owns a whole family of types of its own — the ``snowflake_``-named
data types it renders in addition to the core concepts — and that family has
two members that do **not** follow the ``format_data_type_<name>`` /
``supports_data_type_<name>`` naming convention as unconditional answers,
because they are *conditional*: Snowflake's ``CREATE TYPE`` arrived in server
version 10.8, so before that a user-defined reference cannot be written at all,
and Snowflake's native ``UUID`` arrived in 10.2, so before that there is no
``UUID`` word to write.  A naming pattern cannot express "yes, but only from
10.8", and without a stated shape the family is merely implied by a regex.
This protocol states the two.

Everything else in the family is discovered by convention from the type's own
``name``, exactly as the core :class:`DataTypeSupport` documents, so it is
deliberately not repeated here.
"""

from typing import Protocol, runtime_checkable

from rhosocial.activerecord.backend.dialect.protocols import DataTypeSupport


__all__ = ["SnowflakeTypeSupport"]


@runtime_checkable
class SnowflakeTypeSupport(DataTypeSupport, Protocol):
    """The Snowflake-specific data-type surface of a dialect.

    Extends :class:`DataTypeSupport` because one of the two
    non-conventional members is about a user-defined type: a column of that type
    is written as a qualified *reference* to a name created earlier by
    ``CREATE TYPE``, so the reference is only valid where ``CREATE TYPE`` is.
    """

    def supports_data_type_snowflake_user_defined(self) -> bool:
        """Whether a reference to a user-defined type can be rendered.

        False below Snowflake 10.8, which has no ``CREATE TYPE`` — and so no
        name for the reference to name.  Declaring the gate separately from the
        formatter is what lets
        :meth:`~...mixins.types.SnowflakeTypeSupportMixin.format_data_type_snowflake_user_defined`
        refuse with a version in the message instead of writing DDL the server
        will reject.
        """
        ...

    def supports_data_type_snowflake_uuid(self) -> bool:
        """Whether the native ``UUID`` column type can be rendered.

        False below Snowflake 10.2, which has no ``UUID`` type at all: the
        release notes for 10.2 announce it under "SQL updates" as "New UUID data
        type — This release adds support for the UUID data type."
        (https://docs.snowflake.com/en/release-notes/2026/10_2), and it is
        absent from the manual's inventory before then.

        The gate is separate from the formatter for the same reason the UDT one
        is: :meth:`~...mixins.types.SnowflakeTypeSupportMixin.format_data_type_snowflake_uuid`
        has to refuse with the version in the message rather than write a word
        the server will reject.  It is also what
        :meth:`~...mixins.types.SnowflakeTypeSupportMixin.suggested_data_types`
        switches on — ``SnowflakeUuidType`` from 10.2 on, ``VarCharType`` below it.
        """
        ...