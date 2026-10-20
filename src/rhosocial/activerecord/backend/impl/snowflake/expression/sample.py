# src/rhosocial/activerecord/backend/impl/snowflake/expression/sample.py
"""Snowflake SAMPLE / TABLESAMPLE clause expressions.

Snowflake can sample a table either by row count or by percentage, optionally
with the BERNOULLI or SYSTEM sampling method and a REPEATABLE seed. ``SAMPLE``
and ``TABLESAMPLE`` are synonyms.

Feature Source: Snowflake native (not SQL standard)

Official Documentation:
- SAMPLE / TABLESAMPLE: https://docs.snowflake.com/en/sql-reference/constructs/sample
"""
from enum import Enum
from typing import Optional, Tuple, Union, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.bases import BaseExpression

from .coercion import as_member

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


__all__ = [
    "SnowflakeSampleForm",
    "SnowflakeSamplingMethod",
    "SnowflakeSampleExpression",
]


class SnowflakeSampleForm(str, Enum):
    """Syntactic form of the sampling clause.

    SAMPLE:       the ``SAMPLE`` keyword.
    TABLESAMPLE:  the ``TABLESAMPLE`` keyword (synonym of ``SAMPLE``).
    """
    #: A member *is* the word it carries: ``str()`` and f-string
    #: interpolation must yield the value, not ``ClassName.MEMBER``, or the
    #: rendered SQL and the artifact would carry the Python spelling.
    #: ``(str, Enum)`` alone does not give that -- ``Enum.__str__`` wins --
    #: so it is stated here once.
    __str__ = str.__str__

    SAMPLE = "SAMPLE"
    TABLESAMPLE = "TABLESAMPLE"


class SnowflakeSamplingMethod(str, Enum):
    """Sampling method used by TABLESAMPLE.

    BERNOULLI:  row-level sampling, each row is selected independently.
    SYSTEM:     block-level sampling, faster but less statistically uniform.
    """
    #: A member *is* the word it carries: ``str()`` and f-string
    #: interpolation must yield the value, not ``ClassName.MEMBER``, or the
    #: rendered SQL and the artifact would carry the Python spelling.
    #: ``(str, Enum)`` alone does not give that -- ``Enum.__str__`` wins --
    #: so it is stated here once.
    __str__ = str.__str__

    BERNOULLI = "BERNOULLI"
    SYSTEM = "SYSTEM"


class SnowflakeSampleExpression(BaseExpression):
    """Snowflake SAMPLE / TABLESAMPLE clause expression.

    Attributes:
        form: :class:`SnowflakeSampleForm` — ``SAMPLE`` or ``TABLESAMPLE``.
        count: Row count (``10 ROWS``) or percentage (``0.5``).
        is_percent: Render the count as a percentage rather than ``N ROWS``.
        sampling_method: Optional :class:`SnowflakeSamplingMethod`.
        seed: Optional ``REPEATABLE`` seed value.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        count: Union[int, float],
        *,
        form: SnowflakeSampleForm = SnowflakeSampleForm.SAMPLE,
        is_percent: bool = False,
        sampling_method: Optional[SnowflakeSamplingMethod] = None,
        seed: Optional[int] = None,
    ):
        super().__init__(dialect)
        self.form = as_member(SnowflakeSampleForm, form, parameter="form")
        self.count = count
        self.is_percent = is_percent
        self.sampling_method = as_member(SnowflakeSamplingMethod, sampling_method, parameter="sampling_method")
        self.seed = seed

    def to_sql(self) -> "Tuple[str, tuple]":
        """Generate the SAMPLE / TABLESAMPLE clause SQL.

        Returns:
            Tuple of (clause SQL string, empty params tuple).

        """
        if self.form is SnowflakeSampleForm.TABLESAMPLE:
            return self.dialect.format_tablesample_clause(self)
        return self.dialect.format_sample_clause(self)
