# src/rhosocial/activerecord/backend/impl/snowflake/mixins/namespace.py
"""SnowflakeNamespaceMixin — the namespace levels a Snowflake name may carry.

This is the one place in the backend that answers a *naming* question. Snowflake
has three name parts, ``database.schema.object``, and both levels are rendered,
so the shared objects package's two slots are filled: ``catalog_name`` is the
database and ``schema_name`` the schema. Nothing here invents a fourth level or
a dialect-specific subclass -- the shared renderer emits ``"DB"."SCHEMA"."TABLE"``
from the slots it was handed.

Why the whole naming side lives in one mixin
============================================

It used to be split, and the split was where a bug grew.
``SnowflakeCatalogMixin`` held the three qualification probes while
``SnowflakeSchemaMixin`` held ``supports_schema``, and the two names were close
enough to be confused: two mixins declared ``supports_schema``, both returned
``True``, and both docstrings described the *naming* layer. C3 let the earlier
base win, so the copy that got shadowed was the one whose docstring matched the
method it was defining, and nothing looked wrong from outside. Two names, two
meanings, one of them invisible -- that is the failure mode this file exists to
make impossible.

So the naming side is stated once, here, and
:class:`~...mixins.schema.SnowflakeSchemaMixin` keeps only the DDL-side switch,
where it sits beside the granular ``supports_create_schema`` family it
umbrellas. ``supports_schema`` there answers "may this engine ``CREATE
SCHEMA``"; ``supports_schema_qualification`` here answers "may a name carry
one". Snowflake answers both ``True``, and the other eight dialects answer their
own pair the same way, so the two questions coincide here by agreement rather
than by accident.

Snowflake is the dialect where the two levels are genuinely separable
===================================================================

A database exists and is rendered, but never on its own: Snowflake resolves
``db.object`` nowhere, because a database contains only schemas. That single
rule is this mixin's real contribution and it lives in
:meth:`validate_catalog_name`, since it is about whether the levels the caller
supplied can form a name at all.

The spelling -- which levels appear, and in what order -- needs no override
here. Core's :meth:`~...schema_namespace.NamespaceMixin.format_qualified_name`
already emits exactly ``[database, schema, name]`` joined by
:attr:`~...schema_namespace.NamespaceMixin.separator`, which is Snowflake's own
answer. Restating it would put the same statement in two files, and the two
could drift: the mixin would promise a level the inherited method stopped
emitting, and nothing would notice until a name rendered one level short. So
the dialect states what is *unlike* the default, and the shared method supplies
the part that is not.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.objects import SchemaObject

__all__ = ["SnowflakeNamespaceMixin"]


class SnowflakeNamespaceMixin:
    """Which namespace levels a Snowflake name can be qualified with.

    Every statement that names a catalogue object goes through the shared
    ``format_*_object`` methods, which call
    :meth:`~...schema_namespace.NamespaceMixin.validate_namespace` -- the check
    below -- and then ask the shared renderer for the text.
    """

    def supports_catalog(self) -> bool:
        """Snowflake models a database above the schema."""
        return True

    def supports_catalog_qualification(self) -> bool:
        """Snowflake renders the database when a name carries one.

        ``db.schema.table`` is the normal spelling in Snowflake, not an escape
        hatch, so this is ``True`` where PostgreSQL's is ``False``.
        """
        return True

    def supports_schema_qualification(self) -> bool:
        """Snowflake renders the schema when a name carries one.

        ``schema.table`` is how Snowflake names a relation inside its default
        database, so qualification here is ordinary rather than an escape
        hatch. This is a naming answer and is deliberately separate from the
        DDL-side ``supports_schema``.
        """
        return True

    def validate_catalog_name(self, expr: "SchemaObject") -> None:
        """Accept or reject the database *expr* carries.

        Every object this dialect names is a *schema-level* object: Snowflake
        resolves ``db.object`` nowhere, ``db`` only ever contains schemas. So
        a catalog with no schema cannot become valid SQL and is rejected here
        rather than rendered as a name the server would refuse.

        The check runs while rendering, not while constructing, because only
        then is the dialect -- and therefore what this dialect can express --
        known. That is the same rule the expression constructors used to
        apply, now stated once by the dialect instead of by each caller.

        Args:
            expr: The schema object being rendered.

        Raises:
            ValueError: *expr* carries a database but no schema.
        """
        if expr.catalog_name and not expr.schema_name:
            raise ValueError(
                f"Snowflake renders {expr.catalog_name!r} only together with a "
                f"schema; {type(expr).__name__} {expr.name!r} has no schema_name"
            )