"""Snowflake-specific type definitions and helpers.

This module provides type-safe helpers for Snowflake-specific data types
such as VARIANT and ARRAY.
"""
from typing import Any, Dict, List, Optional


class SnowflakeVariant:
    """Helper class for Snowflake VARIANT type.

    VARIANT is Snowflake's universal semi-structured data type that can
    store JSON, Avro, ORC, Parquet, and XML data.

    Example:
        >>> variant = SnowflakeVariant({"key": "value"})
        >>> variant.value
        {'key': 'value'}
    """

    def __init__(self, value: Any = None):
        self.value = value

    def to_database(self) -> Any:
        """Convert to database representation."""
        return self.value

    def __repr__(self) -> str:
        return f"SnowflakeVariant(value={self.value!r})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SnowflakeVariant):
            return self.value == other.value
        return self.value == other

    def __hash__(self) -> int:
        try:
            return hash(str(self.value))
        except TypeError:
            return id(self)


class SnowflakeArray:
    """Helper class for Snowflake ARRAY type.

    ARRAY is Snowflake's ordered sequence of elements of the same type.

    Example:
        >>> arr = SnowflakeArray([1, 2, 3])
        >>> arr.elements
        [1, 2, 3]
    """

    def __init__(self, elements: Optional[List[Any]] = None):
        self.elements = elements or []

    def to_database(self) -> List[Any]:
        """Convert to database representation."""
        return self.elements

    def __repr__(self) -> str:
        return f"SnowflakeArray(elements={self.elements!r})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SnowflakeArray):
            return self.elements == other.elements
        return self.elements == other

    def __len__(self) -> int:
        return len(self.elements)

    def __getitem__(self, index: int) -> Any:
        return self.elements[index]
