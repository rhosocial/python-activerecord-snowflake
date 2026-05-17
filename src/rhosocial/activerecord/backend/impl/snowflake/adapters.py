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

    Snowflake supports three timestamp variants:
    - TIMESTAMP_LTZ: Local timezone — stored in UTC, displayed in local TZ
    - TIMESTAMP_NTZ: No timezone — stored and displayed as-is
    - TIMESTAMP_TZ: With timezone — preserves the original timezone offset

    The ``timestamp_type`` option controls behavior:
    - "ntz" (default): Naive datetimes, no TZ conversion
    - "ltz": Convert to UTC for storage, display in session TZ
    - "tz": Preserve timezone offset alongside the timestamp
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
        import datetime
        if not isinstance(value, datetime.datetime):
            return value

        ts_type = (options or {}).get("timestamp_type", "ntz")
        if ts_type == "ltz":
            # LTZ: normalize to UTC for storage
            if value.tzinfo is not None:
                value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        elif ts_type == "tz":
            # TZ: ensure timezone-aware for Snowflake to preserve offset
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
        # NTZ: store as-is
        return value

    def from_database(
        self, value: Any, target_type: Type, options: Optional[Dict[str, Any]] = None
    ) -> Any:
        if value is None:
            return None
        import datetime
        if not isinstance(value, datetime.datetime):
            if isinstance(value, str):
                # Attempt ISO format parse
                try:
                    value = datetime.datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    return value
            else:
                return value

        ts_type = (options or {}).get("timestamp_type", "ntz")
        if ts_type == "ltz":
            # LTZ: database returns UTC, attach UTC tzinfo for proper local conversion
            if value.tzinfo is None:
                value = value.replace(tzinfo=datetime.timezone.utc)
        elif ts_type == "tz":
            # TZ: value already carries timezone from Snowflake
            pass
        # NTZ: return as-is (naive datetime)
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
