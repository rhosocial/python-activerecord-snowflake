# src/rhosocial/activerecord/backend/impl/snowflake/expression/sequence.py
"""Snowflake's sequence value reference: ``<sequence>.NEXTVAL``.

A sequence is not a relation (core's ``Sequence`` object says so), and it is
not reached through a function either: Snowflake reads the next value from a
*property* on the sequence, ``seq.nextval``, where PostgreSQL's spelling is
``nextval('seq')``. Both are ``SequenceNextval``-class operations, but the SQL
they share no more than the name, so the node is this backend's own and its
kind names the backend first.

The node carries the alias too, because the only reason a statement calls it is
to name the value it returns -- ``SELECT my_seq.NEXTVAL AS next_id`` -- and an
alias applied by a caller would be SQL text built outside a formatter.
"""

from typing import TYPE_CHECKING, Optional

from rhosocial.activerecord.backend.expression.bases import AliasableMixin, SQLValue

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase

__all__ = ["SnowflakeNextvalExpression"]


class SnowflakeNextvalExpression(AliasableMixin, SQLValue):
    """``<sequence>.NEXTVAL`` -- the next value of a Snowflake sequence.

    Attributes:
        sequence: The sequence's name, as it is written before the dot.
        alias: Optional name for the value, rendered as ``AS <alias>``.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        sequence: str,
        alias: Optional[str] = None,
    ):
        super().__init__(dialect)
        if not isinstance(sequence, str) or not sequence:
            raise ValueError("NEXTVAL requires a non-empty sequence name")
        self.sequence = sequence
        self.alias = alias

    @property
    def format_method(self) -> str:
        """The dialect formatting method that renders this expression."""
        return "format_snowflake_nextval_expression"
