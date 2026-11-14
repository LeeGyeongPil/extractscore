"""Quality gates for CI: minimum F1 overall and per field."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import InputError
from .score import Report


@dataclass(frozen=True)
class GateFailure:
    """One field that is below its required F1."""

    path: str
    f1: float
    minimum: float


def check_gates(
    report: Report,
    *,
    min_f1: float | None = None,
    field_min: dict[str, float] | None = None,
) -> list[GateFailure]:
    """Return the fields below their threshold (empty list means the gate passes).

    ``min_f1`` applies to every scored field; ``field_min`` overrides it for one path.
    A path in ``field_min`` that never appears in the report is an ``InputError`` so a
    typo cannot silently pass.
    """
    field_min = field_min or {}
    for path in field_min:
        if path not in report.fields:
            raise InputError("err_unknown_field", path=path, known=", ".join(report.fields) or "-")
    failures: list[GateFailure] = []
    for path, stats in report.fields.items():
        minimum = field_min.get(path, min_f1)
        if minimum is None or stats.f1 is None:
            continue
        if stats.f1 + 1e-12 < minimum:
            failures.append(GateFailure(path, stats.f1, minimum))
    return failures
