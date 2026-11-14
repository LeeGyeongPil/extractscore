"""Counts and precision / recall / F1 with an explicit 0/0 rule.

    precision = TP / (TP + FP)        None when the denominator is 0
    recall    = TP / (TP + FN)        None when the denominator is 0
    F1        = 2TP / (2TP + FP + FN) None when the denominator is 0

``None`` means "nothing to measure", which is different from a score of 0.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

ERROR_CATEGORIES = ("wrong_value", "type_error", "missing", "hallucinated", "parse_failure")


@dataclass
class Counts:
    """True/false positives and negatives, plus how many times each error category occurred."""

    tp: int = 0
    fp: int = 0
    fn: int = 0
    errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add_event(self, kind: str) -> None:
        """Record one scoring event: ``tp`` or one of ``ERROR_CATEGORIES``."""
        if kind == "tp":
            self.tp += 1
            return
        if kind in ("wrong_value", "type_error"):
            self.fp += 1
            self.fn += 1
        elif kind in ("missing", "parse_failure"):
            self.fn += 1
        elif kind == "hallucinated":
            self.fp += 1
        else:  # pragma: no cover - programming error
            raise ValueError(f"unknown event kind {kind!r}")
        self.errors[kind] += 1

    def merge(self, other: "Counts") -> None:
        """Add another ``Counts`` into this one."""
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn
        for kind, number in other.errors.items():
            self.errors[kind] += number

    @property
    def error_count(self) -> int:
        """Number of error events (a wrong value is one event although it is FP+FN)."""
        return sum(self.errors.values())

    @property
    def precision(self) -> float | None:
        return _ratio(self.tp, self.tp + self.fp)

    @property
    def recall(self) -> float | None:
        return _ratio(self.tp, self.tp + self.fn)

    @property
    def f1(self) -> float | None:
        return _ratio(2 * self.tp, 2 * self.tp + self.fp + self.fn)

    @property
    def is_correct(self) -> bool:
        """Something was scored and nothing was wrong."""
        return self.tp > 0 and self.fp == 0 and self.fn == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "errors": {k: v for k, v in sorted(self.errors.items()) if v},
        }


@dataclass
class FieldStats:
    """Counts for one field path, with the comparator type that was used."""

    path: str
    type: str | None = None
    counts: Counts = field(default_factory=Counts)

    @property
    def precision(self) -> float | None:
        return self.counts.precision

    @property
    def recall(self) -> float | None:
        return self.counts.recall

    @property
    def f1(self) -> float | None:
        return self.counts.f1

    def to_dict(self) -> dict[str, Any]:
        data = {"type": self.type}
        data.update(self.counts.to_dict())
        return data


def macro_f1(stats: list[FieldStats]) -> float | None:
    """Mean of the field F1 scores that are not ``None``."""
    values = [s.f1 for s in stats if s.f1 is not None]
    return sum(values) / len(values) if values else None


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None
