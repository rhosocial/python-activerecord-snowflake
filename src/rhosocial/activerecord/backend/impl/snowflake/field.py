"""Snowflake Sequence-based Primary Key Mixin.

Provides Snowflake-native SEQUENCE-based integer primary key generation.
Unlike AUTOINCREMENT, SEQUENCE pre-allocation guarantees the PK value
is known before INSERT, avoiding the need for RETURNING clause or
last_insert_id fallbacks.
"""
from typing import ClassVar, Dict, Any, Optional

from pydantic import Field


class SnowflakePKMixin:
    """Snowflake Sequence-based integer primary key Mixin.

    Pre-allocates a SEQUENCE value via NEXTVAL before INSERT,
    ensuring the primary key is known prior to the INSERT statement.
    This avoids reliance on AUTOINCREMENT + last_insert_id or
    RETURNING clause, both of which have limitations on Snowflake.

    Usage:
        class Order(SnowflakePKMixin, TimestampMixin, ActiveRecord):
            _snowflake_sequence_name: ClassVar[str] = "order_id_seq"
            # id field is automatically provided by this Mixin

    Prerequisite:
        CREATE SEQUENCE order_id_seq START = 1 INCREMENT = 1;

    For high-throughput scenarios, consider batch NEXTVAL pre-fetch:
        SELECT seq.NEXTVAL FROM TABLE(GENERATOR(ROWCOUNT => N))
    """

    id: Optional[int] = Field(default=None)

    _snowflake_sequence_name: ClassVar[str] = "default_id_seq"

    def prepare_save_data(self, data: Dict[str, Any], is_new: bool) -> Dict[str, Any]:
        """Pre-fetch SEQUENCE value and inject into save data for new records."""
        pk_field = self.primary_key()

        if is_new and data.get(pk_field) is None:
            backend = self.__class__.backend()
            if backend is not None:
                seq_name = self.__class__._snowflake_sequence_name
                result = backend.execute(
                    f"SELECT {seq_name}.NEXTVAL AS next_id", ()
                )
                if result.data and len(result.data) > 0:
                    next_id = result.data[0].get("NEXT_ID") or result.data[0].get("next_id")
                    if next_id is not None:
                        data[pk_field] = int(next_id)
                        setattr(self, pk_field, data[pk_field])

        parent_prepare = super().prepare_save_data if hasattr(super(), "prepare_save_data") else None
        if parent_prepare:
            data = parent_prepare(data, is_new)

        return data
