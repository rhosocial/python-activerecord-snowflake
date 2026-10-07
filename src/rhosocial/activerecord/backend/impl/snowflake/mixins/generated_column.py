# src/rhosocial/activerecord/backend/impl/snowflake/mixins/generated_column.py
"""Snowflake generated column support mixin."""

from typing import Tuple

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError


class SnowflakeGeneratedColumnMixin:
    """Snowflake generated (computed) column support."""

    def format_identity_clause(self, expr) -> Tuple[str, tuple]:
        """Render Snowflake's ``IDENTITY(seed, step)`` column property.

        The reference grammar spells the property ``{ AUTOINCREMENT | IDENTITY }
        [ ( start_num , step_num ) | START <num> INCREMENT <num> ]
        [ { ORDER | NOORDER } ]``; this dialect renders the parenthesised
        ``IDENTITY`` spelling, which is the same shape SQL Server uses. Both
        values default to ``1``, the reference's own default.

        ``ORDER | NOORDER`` sits *after* the parenthesis group, not inside it:
        `` IDENTITY(1, 1) NOORDER``. The word comes from
        :meth:`identity_order_keyword` -- this dialect spells the negative form
        ``NOORDER``, one word -- and :meth:`supports_identity_order` gates it.

        Each two-spelling option carries one parameter per spelling --
        ``cycle`` / ``no_cycle``, ``cache`` / ``no_cache``, ``order`` /
        ``no_order``. An unset pair renders nothing; a requested spelling whose
        probe answers ``False`` is refused by name, and the two negative
        parameters are checked exactly like the positive ones, so
        ``no_cycle=True`` / ``no_cache=True`` / ``no_order=True`` are never
        silently dropped.

        The clause is gated option by option, exactly like core's SQL-standard
        formatter, so an option this dialect cannot express is refused by name
        rather than silently dropped:

        * :meth:`supports_identity_column` gates the clause as a whole;
        * :meth:`supports_identity_generation_always` gates ``ALWAYS``. This
          dialect answers ``False``: Snowflake has no ``GENERATED ALWAYS``
          form, and rendering ``IDENTITY`` for an ``ALWAYS`` request would
          downgrade its meaning (``ALWAYS`` rejects user-supplied values,
          ``IDENTITY`` accepts them), so the request is refused;
        * :meth:`supports_identity_start` / ``_increment`` gate the two
          parameters Snowflake does accept;
        * :meth:`supports_identity_order` gates the ``ORDER`` / ``NOORDER``
          tail Snowflake does accept;
        * :meth:`supports_identity_minvalue` / ``_maxvalue`` / ``_cycle`` /
          ``_cache`` gate the options Snowflake's grammar does not have.

        Raises:
            UnsupportedFeatureError: The dialect cannot express the clause, the
                requested generation mode, or one of the requested options.
        """
        if not self.supports_identity_column():
            raise UnsupportedFeatureError(
                self.name,
                "IDENTITY column",
                f"{self.name} does not support IDENTITY columns.",
            )
        generation = (expr.generation or "BY DEFAULT").upper()
        if generation == "ALWAYS" and not self.supports_identity_generation_always():
            raise UnsupportedFeatureError(
                self.name,
                "IDENTITY GENERATED ALWAYS",
                f"{self.name} cannot express GENERATED ALWAYS for an identity "
                f"column; only BY DEFAULT is available.",
            )
        if expr.start is not None and not self.supports_identity_start():
            raise UnsupportedFeatureError(
                self.name,
                "IDENTITY START",
                f"{self.name} does not support the START WITH identity option.",
            )
        if expr.increment is not None and not self.supports_identity_increment():
            raise UnsupportedFeatureError(
                self.name,
                "IDENTITY INCREMENT",
                f"{self.name} does not support the INCREMENT BY identity option.",
            )
        if expr.minvalue is not None and not self.supports_identity_minvalue():
            raise UnsupportedFeatureError(
                self.name,
                "IDENTITY MINVALUE",
                f"{self.name} does not support the MINVALUE identity option.",
            )
        if expr.maxvalue is not None and not self.supports_identity_maxvalue():
            raise UnsupportedFeatureError(
                self.name,
                "IDENTITY MAXVALUE",
                f"{self.name} does not support the MAXVALUE identity option.",
            )
        if (expr.cycle or expr.no_cycle) and not self.supports_identity_cycle():
            raise UnsupportedFeatureError(
                self.name,
                "IDENTITY CYCLE",
                f"{self.name} does not support the CYCLE identity option.",
            )
        if (expr.cache is not None or expr.no_cache) and not self.supports_identity_cache():
            raise UnsupportedFeatureError(
                self.name,
                "IDENTITY CACHE",
                f"{self.name} does not support the CACHE identity option.",
            )
        if (expr.order or expr.no_order) and not self.supports_identity_order():
            raise UnsupportedFeatureError(
                self.name,
                "IDENTITY ORDER",
                f"{self.name} does not support the ORDER identity option.",
            )
        start = expr.start if expr.start is not None else 1
        increment = expr.increment if expr.increment is not None else 1
        sql = f" IDENTITY({start}, {increment})"
        if expr.order or expr.no_order:
            # Snowflake's tail follows the parenthesis group:
            # IDENTITY [ ( start , step ) ] [ ORDER | NOORDER ].
            sql += f" {self.identity_order_keyword(expr.order)}"
        return sql, ()

    def identity_order_keyword(self, order: bool) -> str:
        """Snowflake spells the negative order setting ``NOORDER``, one word.

        Core's hook defaults to the SQL-standard ``ORDER`` / ``NO ORDER``; the
        reference's identity tail is ``[ { ORDER | NOORDER } ]``, so this
        dialect overrides the spelling hook and the formatter above keeps the
        gating. Placed beside the formatter because both are the identity
        clause's Snowflake grammar; ``SnowflakeGeneratedColumnMixin`` precedes
        ``IdentityColumnMixin`` in the dialect's base list, so this override
        wins.

        Core's cache spelling hook was split (``identity_cache_keyword`` now
        spells positive counts only and ``identity_no_cache_keyword`` carries
        the negative); this dialect overrides neither, because it declares no
        cache support at all and refuses both spellings before any hook is
        consulted. The order hook's signature is unchanged, so this override
        still attaches where the formatter calls it.

        https://docs.snowflake.com/en/sql-reference/sql/create-table
        """
        return "ORDER" if order else "NOORDER"

    def supports_generated_columns(self) -> bool:
        """Snowflake supports generated (computed) columns."""
        return True

    def supports_stored_generated_columns(self) -> bool:
        """Snowflake generated columns are virtual only; STORED is unsupported."""
        return False

    def supports_virtual_generated_columns(self) -> bool:
        """Snowflake exposes generated columns as virtual columns."""
        return True


__all__ = ['SnowflakeGeneratedColumnMixin']
