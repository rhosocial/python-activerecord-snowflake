"""Snowflake backend type adapters.

This module provides type adapters for Snowflake-specific data types,
converting between Python types and Snowflake database types.
"""
import json
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional, Type, Union

from rhosocial.activerecord.backend.type_adapter import SQLTypeAdapter
from .types import SnowflakeVariant, SnowflakeArray


class SnowflakeVariantAdapter(SQLTypeAdapter):
    """Adapts Python dict/list to Snowflake VARIANT and vice-versa.

    Snowflake VARIANT type stores semi-structured data natively.
    The connector typically returns Python dict/list directly.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {dict: [str], list: [str]}

    def to_database(
        self, value: Union[dict, list], target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Optional[Union[dict, list]]:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)


class SnowflakeArrayAdapter(SQLTypeAdapter):
    """Adapts Python list to Snowflake ARRAY and vice-versa.

    Snowflake ARRAY type stores ordered sequences natively.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {list: [str]}

    def to_database(
        self, value: list, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        if isinstance(value, list):
            return json.dumps(value, ensure_ascii=False)
        return value

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Optional[list]:
        if value is None:
            return None
        if isinstance(value, list):
            return value
        return json.loads(value)


class SnowflakeTimestampAdapter(SQLTypeAdapter):
    """Adapts Python datetime to Snowflake TIMESTAMP types.

    Snowflake supports multiple timestamp types:
    - TIMESTAMP_LTZ (local timezone)
    - TIMESTAMP_NTZ (no timezone)
    - TIMESTAMP_TZ (with timezone)
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        import datetime
        return {datetime.datetime: [str]}

    def to_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        return value

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        return value


class SnowflakeBooleanAdapter(SQLTypeAdapter):
    """Adapts Python bool to Snowflake BOOLEAN and vice-versa.

    Snowflake BOOLEAN type maps directly to Python bool.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {bool: [int, str]}

    def to_database(
        self, value: bool, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        return value

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        return bool(value)


class SnowflakeDecimalAdapter(SQLTypeAdapter):
    """Adapts Python Decimal to Snowflake NUMBER/DECIMAL and vice-versa.

    Snowflake NUMBER(p, s) type maps to Python Decimal for precision.
    """

    @property
    def supported_types(self) -> Dict[Type, List[Any]]:
        return {Decimal: [float, str, int]}

    def to_database(
        self, value: Decimal, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return float(value)
        return value

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
