# src/rhosocial/activerecord/backend/impl/snowflake/_scan.py
"""Character scanners for the short, fixed-shape strings this backend reads.

``src`` holds no regular expressions: a pattern has to be read twice (once as
itself, once as the string shape it accepts), and its anchoring and boundary
rules are the part that breaks quietly.  Every shape read here -- a leading type
word, its parameters, a quoted type name -- is short enough that scanning the
characters states the accepted set outright.  Each helper names the character
class it treats as part of a word, a number, a separator or a quoted name, so
the reading and the rule are the same sentence.

These helpers reproduce the exact classes a pattern would have used: a word
character is alphanumeric or ``_`` (``\\w``), whitespace is ``str.isspace``
(``\\s``), a digit is a decimal digit (``\\d``).
"""

from typing import List, Optional, Tuple


def is_word_char(ch: str) -> bool:
    """Return whether ``ch`` continues a word: alphanumeric or underscore."""
    return ch.isalnum() or ch == "_"


def leading_word(text: str, start: int = 0) -> Tuple[str, int]:
    """Read the word run beginning at ``start``.

    Returns ``(word, end)``, where ``end`` is the offset just past the run.
    An empty word and ``start`` itself come back when no word begins there.
    """
    pos = start
    length = len(text)
    while pos < length and is_word_char(text[pos]):
        pos += 1
    return text[start:pos], pos


def skip_whitespace(text: str, start: int) -> int:
    """Return the offset of the first non-whitespace character at or after ``start``."""
    pos = start
    length = len(text)
    while pos < length and text[pos].isspace():
        pos += 1
    return pos


def word_runs(text: str) -> List[str]:
    """List the maximal word runs in ``text``; separators are dropped."""
    runs: List[str] = []
    pos = 0
    length = len(text)
    while pos < length:
        if is_word_char(text[pos]):
            word, pos = leading_word(text, pos)
            runs.append(word)
        else:
            pos += 1
    return runs


def contains_word(text: str, word: str) -> bool:
    """Return whether ``text`` carries ``word`` as a whole word, ignoring case.

    A whole word is a run that equals ``word``: ``XUNSIGNED`` does not carry
    ``UNSIGNED``, because a word boundary cannot fall inside a run.
    """
    target = word.upper()
    return any(token.upper() == target for token in word_runs(text))


def decimal_runs(text: str) -> List[str]:
    """List the runs of decimal digits in ``text``, left to right."""
    runs: List[str] = []
    pos = 0
    length = len(text)
    while pos < length:
        if text[pos].isdecimal():
            end = pos + 1
            while end < length and text[end].isdecimal():
                end += 1
            runs.append(text[pos:end])
            pos = end
        else:
            pos += 1
    return runs


def first_decimal_after_open_paren(text: str) -> Optional[str]:
    """Return the first digit run that immediately follows ``(``, or ``None``.

    Only ``(`` with a digit directly after it counts: ``VARCHAR (10)`` is not
    the parameter list shape that a type spelling writes.
    """
    length = len(text)
    for pos in range(length - 1):
        if text[pos] == "(" and text[pos + 1].isdecimal():
            end = pos + 1
            while end < length and text[end].isdecimal():
                end += 1
            return text[pos + 1:end]
    return None


def quoted_qualified_name(text: str) -> Optional[List[str]]:
    """Read a quoted, dot-qualified name that occupies the whole of ``text``.

    The accepted shape is one to three double-quoted, non-empty names separated
    by a dot, with optional whitespace around each dot: ``"a"``, ``"a"."b"``,
    ``"db"."s"."t"``.  Returns the quoted contents in order, or ``None`` when
    ``text`` is anything else (an unquoted name, an empty ``""``, four parts,
    trailing text).
    """
    parts: List[str] = []
    pos = 0
    length = len(text)
    while True:
        if pos >= length or text[pos] != '"':
            return None
        closing = text.find('"', pos + 1)
        if closing <= pos + 1:  # no closing quote, or an empty name
            return None
        parts.append(text[pos + 1:closing])
        pos = closing + 1
        if pos == length:
            return parts
        pos = skip_whitespace(text, pos)
        if pos >= length or text[pos] != ".":
            return None
        if len(parts) >= 3:  # a fourth name is a different shape
            return None
        pos = skip_whitespace(text, pos + 1)


__all__ = [
    "contains_word",
    "decimal_runs",
    "first_decimal_after_open_paren",
    "is_word_char",
    "leading_word",
    "quoted_qualified_name",
    "skip_whitespace",
    "word_runs",
]
