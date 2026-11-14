"""Typed value comparators.

Each comparator answers one question: is the predicted value the same as the gold
value, once format noise is removed?  The answer is one of three outcomes:

* ``"match"``      - same value
* ``"wrong"``      - a different value
* ``"type_error"`` - the predicted value cannot be read as the field's type
                     (``"N/A"`` in a number field, an object in a date field...)
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Sequence

from .config import FieldRule

MATCH = "match"
WRONG = "wrong"
TYPE_ERROR = "type_error"

_CURRENCY = re.compile(r"usd|krw|eur|gbp|jpy|[$€£₩¥원\s,]", re.IGNORECASE)
_TRUE = {"true", "yes", "y", "1"}
_FALSE = {"false", "no", "n", "0"}


def is_empty(value: Any, empty_as_null: bool = True) -> bool:
    """True for ``None``; with ``empty_as_null`` also ``""``, ``[]`` and ``{}``."""
    if value is None:
        return True
    if not empty_as_null:
        return False
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return not value
    return False


def to_number(value: Any) -> float | None:
    """Read a number from an int/float or a string such as ``"$1,250.00"`` or ``"12,000원"``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        cleaned = _CURRENCY.sub("", value)
        try:
            number = float(cleaned)
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def to_date(value: Any, formats: Sequence[str]) -> date | None:
    """Parse a date string with the first format that fits (order matters for ``11/03/2026``)."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_bool(value: Any) -> bool | None:
    """Read a bool from a JSON bool or common strings (true/false/yes/no/1/0)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
    return None


def normalise_text(value: Any, casefold: bool = True) -> str:
    """Collapse whitespace and (optionally) ignore case."""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text.casefold() if casefold else text


def levenshtein(a: str, b: str) -> int:
    """Edit distance between two strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1]


def text_similarity(a: str, b: str) -> float:
    """1.0 for identical strings, falling with edit distance (normalised by the longer one)."""
    longest = max(len(a), len(b))
    return 1.0 if longest == 0 else 1.0 - levenshtein(a, b) / longest


def _is_container(value: Any) -> bool:
    return isinstance(value, (dict, list))


def compare_values(rule: FieldRule, gold: Any, pred: Any, date_formats: Sequence[str]) -> str:
    """Compare two non-empty scalar values under ``rule`` and return the outcome."""
    kind = rule.type or "text"
    if _is_container(pred):
        return TYPE_ERROR

    if kind == "number":
        gold_n = to_number(gold)
        if gold_n is None:  # unreadable gold: fall back to plain text equality
            return MATCH if normalise_text(gold) == normalise_text(pred) else WRONG
        pred_n = to_number(pred)
        if pred_n is None:
            return TYPE_ERROR
        return MATCH if math.isclose(gold_n, pred_n, rel_tol=1e-9, abs_tol=max(rule.tol, 1e-12)) else WRONG

    if kind == "date":
        gold_d = to_date(gold, date_formats)
        if gold_d is None:
            return MATCH if normalise_text(gold) == normalise_text(pred) else WRONG
        pred_d = to_date(pred, date_formats)
        if pred_d is None:
            return TYPE_ERROR
        return MATCH if gold_d == pred_d else WRONG

    if kind == "bool":
        gold_b = to_bool(gold)
        if gold_b is None:
            return MATCH if normalise_text(gold) == normalise_text(pred) else WRONG
        pred_b = to_bool(pred)
        if pred_b is None:
            return TYPE_ERROR
        return MATCH if gold_b == pred_b else WRONG

    if kind == "id":  # exact match; only surrounding whitespace is ignored
        return MATCH if str(gold).strip() == str(pred).strip() else WRONG

    if kind == "enum":
        return MATCH if normalise_text(gold) == normalise_text(pred) else WRONG

    # text
    casefold = True if rule.casefold is None else rule.casefold
    a, b = normalise_text(gold, casefold), normalise_text(pred, casefold)
    if a == b:
        return MATCH
    if rule.fuzzy is not None and text_similarity(a, b) >= rule.fuzzy:
        return MATCH
    return WRONG
