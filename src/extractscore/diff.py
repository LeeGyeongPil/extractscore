"""Compare two runs scored against the same gold set."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import InputError
from .i18n import ref
from .metrics import FieldStats
from .score import Report

IMPROVED = "improved"
REGRESSED = "regressed"
SAME = "same"


@dataclass
class FieldDelta:
    """F1 of one field in run A and run B.

    A field that does not appear in a run had nothing to score there, so for the
    status it counts as perfect (1.0) - a field that only shows up in B because of a
    hallucination is therefore a regression.
    """

    path: str
    type: str | None
    a: FieldStats | None
    b: FieldStats | None
    delta: float
    status: str

    @property
    def f1_a(self) -> float | None:
        return None if self.a is None else self.a.f1

    @property
    def f1_b(self) -> float | None:
        return None if self.b is None else self.b.f1


@dataclass
class Flip:
    """A field of one document that changed between runs."""

    doc: str
    path: str
    direction: str  # "correct->wrong" or "wrong->correct"


@dataclass
class Diff:
    fields: dict[str, FieldDelta]
    flips: list[Flip]
    micro_a: FieldStats
    micro_b: FieldStats
    tolerance: float = 0.0
    parse_failures: tuple[int, int] = (0, 0)
    skipped: list[str] = field(default_factory=list)
    documents: int = 0

    @property
    def regressions(self) -> list[str]:
        """Field paths whose F1 fell by more than the tolerance."""
        return [p for p, d in self.fields.items() if d.status == REGRESSED]

    @property
    def improvements(self) -> list[str]:
        return [p for p, d in self.fields.items() if d.status == IMPROVED]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tolerance": self.tolerance,
            "fields": {
                p: {
                    "type": d.type,
                    "f1_a": d.f1_a,
                    "f1_b": d.f1_b,
                    "delta": d.delta,
                    "status": d.status,
                    "errors_a": {} if d.a is None else d.a.to_dict()["errors"],
                    "errors_b": {} if d.b is None else d.b.to_dict()["errors"],
                }
                for p, d in self.fields.items()
            },
            "micro": {"a": self.micro_a.counts.to_dict(), "b": self.micro_b.counts.to_dict()},
            "parse_failures": {"a": self.parse_failures[0], "b": self.parse_failures[1]},
            "regressions": self.regressions,
            "flips": [{"doc": f.doc, "field": f.path, "direction": f.direction} for f in self.flips],
        }

    def to_markdown(self, lang: str = "en") -> str:
        from .render import diff_markdown

        return diff_markdown(self, lang)


def diff(report_a: Report, report_b: Report, *, tolerance: float = 0.0) -> Diff:
    """Compare run A (before) with run B (after).

    A field regresses when its F1 drops by *more than* ``tolerance``; it improves when
    it rises by more than ``tolerance``.  Both reports must come from the same gold set.
    """
    if tolerance < 0:
        raise InputError("err_bad_option", detail=ref("d_tolerance_negative"))
    if set(report_a.doc_ids) != set(report_b.doc_ids):
        raise InputError("err_diff_docs")

    fields: dict[str, FieldDelta] = {}
    for path in sorted(set(report_a.fields) | set(report_b.fields)):
        a, b = report_a.fields.get(path), report_b.fields.get(path)
        f1_a = 1.0 if a is None or a.f1 is None else a.f1
        f1_b = 1.0 if b is None or b.f1 is None else b.f1
        delta = f1_b - f1_a
        status = REGRESSED if delta < -tolerance - 1e-12 else IMPROVED if delta > tolerance + 1e-12 else SAME
        fields[path] = FieldDelta(path, (a or b).type if (a or b) else None, a, b, delta, status)  # type: ignore[union-attr]

    docs_b = {d.id: d for d in report_b.docs}
    flips: list[Flip] = []
    for doc_a in report_a.docs:
        doc_b = docs_b[doc_a.id]
        for path in sorted(set(doc_a.fields) | set(doc_b.fields)):
            ok_a = _ok(doc_a.fields.get(path))
            ok_b = _ok(doc_b.fields.get(path))
            if ok_a and not ok_b:
                flips.append(Flip(doc_a.id or "", path, "correct->wrong"))
            elif ok_b and not ok_a:
                flips.append(Flip(doc_a.id or "", path, "wrong->correct"))

    return Diff(
        fields=fields,
        flips=flips,
        micro_a=report_a.micro,
        micro_b=report_b.micro,
        tolerance=tolerance,
        parse_failures=(report_a.parse_failures, report_b.parse_failures),
        skipped=report_a.skipped,
        documents=len(report_a.docs),
    )


def _ok(stats: FieldStats | None) -> bool:
    """A field with nothing scored in a document counts as fine."""
    return stats is None or stats.counts.is_correct
