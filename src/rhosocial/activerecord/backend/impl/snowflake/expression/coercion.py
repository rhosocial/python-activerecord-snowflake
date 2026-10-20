# src/rhosocial/activerecord/backend/impl/snowflake/expression/coercion.py
"""One place where a closed-set parameter becomes its enum member.

Every enum this package declares inherits ``str`` (org rules §11.3), so a
member *is* the word it carries and an artifact can hold that word. Reading the
artifact back is the mirror of that: the constructor receives the word and must
put the member back, because the parameter's host type is the member and the
formatters read ``.value`` off it.

Rules §10 puts that conversion in the constructor -- "wide in, normalised out"
-- and not in the reader, which only passes parameters by name. The
alternatives both cost something:

* **refusing the word** (``isinstance`` check, ``TypeError``) makes the
  constructor stricter than its own declared type and leaves the node's artifact
  unreadable by the node that produced it. That is a real defect in core's
  datetime and graph enums, which is why the matrix pins those rows; a backend
  enum has no such excuse, because the backend owns both ends.
* **storing the word** lets the value survive and the host type not, so a
  round-trip compares a ``str`` against a member and reports a type mismatch --
  a second spelling of the same problem.

A word outside the set is still refused, by the enum itself and by name.
"""

from enum import Enum
from typing import Any, Optional, Type, TypeVar

_Member = TypeVar("_Member", bound=Enum)


def as_member(
    enum_type: Type[_Member], value: Any, *, parameter: str
) -> Optional[_Member]:
    """*value* as a member of *enum_type*, or ``None`` when it is ``None``.

    Args:
        enum_type: The closed set the parameter declares.
        value: A member, or the word a member carries.
        parameter: The parameter's own name, for the refusal message -- a
            caller reading the error needs to know which argument was wrong,
            and the message cannot recover that from the value alone.

    Returns:
        The member, or ``None`` when *value* is ``None``.

    Raises:
        TypeError: *value* is neither a member nor a string.
        ValueError: *value* is a string the set does not contain.
    """
    if value is None:
        return None
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise TypeError(
            f"{parameter} must be a {enum_type.__name__} or the word it carries, "
            f"got {type(value).__name__}"
        )
    try:
        return enum_type(value)
    except ValueError:
        valid = ", ".join(repr(member.value) for member in enum_type)
        raise ValueError(
            f"{parameter} must be one of {valid}, got {value!r}"
        ) from None


__all__ = ["as_member"]
