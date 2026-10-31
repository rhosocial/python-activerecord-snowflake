# src/rhosocial/activerecord/backend/impl/snowflake/introspection/table_types.py
"""Snowflake's ``INFORMATION_SCHEMA.TABLES.TABLE_TYPE`` vocabulary.

The catalogue's spelling is the fact; the core
:class:`~rhosocial.activerecord.backend.introspection.types.TableType` member
is this backend's reading of it.  Both directions live here so the parser and
the query formatter cannot drift apart: :data:`SNOWFLAKE_TABLE_TYPE_MAP` is the
one table that says which spelling means which member, and
:func:`catalogue_spellings` derives a filter's value list from that same table.

The ``TABLES`` page lists six spellings -- ``BASE TABLE``, ``TEMPORARY TABLE``,
``EXTERNAL TABLE``, ``EVENT TABLE``, ``VIEW`` and ``MATERIALIZED VIEW``
(https://docs.snowflake.com/en/sql-reference/info-schema/tables) -- but
Snowflake has since grown table kinds of its own, each documented as an object
in its own right: Snowflake-managed tables, event tables, Iceberg tables,
hybrid tables and dynamic tables.  Their catalogue spellings are recorded here
rather than being left to an unrecognised-value fallback, because folding one
of them into ``BASE_TABLE`` with no trace is exactly what erases the only
distinction the catalogue made.  The raw spelling survives in
``IntrospectionTableInfo.extra["snowflake_table_type"]``.
"""

from typing import Optional, Tuple

from rhosocial.activerecord.backend.introspection.types import TableType

#: Snowflake's ``TABLE_TYPE`` spellings -> the core member each one means.
#:
#: A kind the core enum has no member for still needs a member, and none of
#: the vendor kinds is a view: they are all tables a caller can select from,
#: so they read as ``BASE_TABLE`` beside their own spelling in ``extra``.
#: ``DYNAMIC TABLE`` is deliberately not ``MATERIALIZED_VIEW``: Snowflake's
#: catalogue distinguishes the two, and reporting a dynamic table as a
#: materialized view would make a listing built with ``include_views=False``
#: return a row whose member says it is a view.
#:
#: https://docs.snowflake.com/en/sql-reference/info-schema/tables
#: https://docs.snowflake.com/en/sql-reference/sql/show-iceberg-tables
#: https://docs.snowflake.com/en/user-guide/dynamic-tables/overview
#: https://docs.snowflake.com/en/user-guide/tables-hybrid
SNOWFLAKE_TABLE_TYPE_MAP = {
    "BASE TABLE": TableType.BASE_TABLE,
    "MANAGED TABLE": TableType.BASE_TABLE,
    "EVENT TABLE": TableType.BASE_TABLE,
    "HYBRID TABLE": TableType.BASE_TABLE,
    "ICEBERG TABLE": TableType.BASE_TABLE,
    "DYNAMIC TABLE": TableType.BASE_TABLE,
    "VIEW": TableType.VIEW,
    "MATERIALIZED VIEW": TableType.MATERIALIZED_VIEW,
    "SYSTEM TABLE": TableType.SYSTEM_TABLE,
    "TEMPORARY TABLE": TableType.TEMPORARY,
    "EXTERNAL TABLE": TableType.EXTERNAL,
}

#: The spellings that are views rather than tables.  ``include_views=False``
#: removes exactly these and leaves every table kind -- including the vendor
#: kinds above -- visible.
SNOWFLAKE_VIEW_TYPES = ("VIEW", "MATERIALIZED VIEW")


def read_table_type(value: Optional[str]) -> str:
    """One row's catalogue spelling, in the catalogue's own case.

    ``TABLE_TYPE`` is documented as a ``VARCHAR`` the catalogue fills in; an
    absent value is read as ``BASE TABLE``, which is what the parser assumed
    before any spelling was recorded.  Upper-casing is how the catalogue
    spells every value, so a fixture that preserved a driver's case still
    matches the map.
    """
    return str(value or "BASE TABLE").strip().upper()


def core_table_type(value: Optional[str]) -> TableType:
    """The core member a catalogue spelling means."""
    return SNOWFLAKE_TABLE_TYPE_MAP.get(read_table_type(value), TableType.BASE_TABLE)


def catalogue_spellings(table_type) -> Tuple[str, ...]:
    """The catalogue spellings one requested ``table_type`` selects.

    Three answers, in this order of authority:

    * an exact catalogue spelling -- ``"ICEBERG TABLE"``, ``"VIEW"`` --
      selects exactly that spelling, so a caller can filter on the raw
      vocabulary the catalogue reported;
    * a core ``TableType`` name or member -- ``"MATERIALIZED_VIEW"``,
      ``"EXTERNAL"`` -- expands onto every spelling mapped to that member,
      which is how a caller who never saw Snowflake's vocabulary asks for a
      kind;
    * a spelling this backend does not know is passed through unchanged, the
      way the formatter used to treat every value, so a kind Snowflake adds
      later is filterable before this table learns it.

    A core kind the catalogue has no spelling for -- ``FOREIGN_TABLE``,
    ``PARTITIONED_TABLE`` -- answers with an empty tuple.  The formatter turns
    that into a comparison that cannot hold rather than dropping the
    condition and answering with every table.
    """
    if isinstance(table_type, TableType):
        return tuple(
            spelling
            for spelling, member in SNOWFLAKE_TABLE_TYPE_MAP.items()
            if member is table_type
        )
    if not table_type:
        return ()
    raw = str(table_type).strip().upper()
    if raw in SNOWFLAKE_TABLE_TYPE_MAP:
        return (raw,)
    member = TableType.__members__.get(raw)
    if member is not None:
        return tuple(
            spelling
            for spelling, mapped in SNOWFLAKE_TABLE_TYPE_MAP.items()
            if mapped is member
        )
    return (raw,)
