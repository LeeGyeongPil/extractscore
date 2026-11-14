"""Text renderers: terminal table, Markdown (JSON lives in ``to_dict``)."""

from __future__ import annotations

import unicodedata
from typing import Sequence

from .diff import Diff
from .gate import GateFailure
from .i18n import t, title_diff, title_score
from .score import Report


def _num(value: float | None, lang: str) -> str:
    return t(lang, "na") if value is None else f"{value:.3f}"


def _errors(stats) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(stats.counts.errors.items()) if v) or "-"


def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _pad(text: str, width: int, right: bool = False) -> str:
    gap = " " * max(width - _width(text), 0)
    return gap + text if right else text + gap


def _table(header: Sequence[str], rows: Sequence[Sequence[str]], numeric: range) -> list[str]:
    widths = [max(_width(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
    lines = []
    for row in [header, *rows]:
        cells = [_pad(str(c), widths[i], right=i in numeric) for i, c in enumerate(row)]
        lines.append("  ".join(cells).rstrip())
    lines.insert(1, "  ".join("-" * w for w in widths))
    return lines


def _md_table(header: Sequence[str], rows: Sequence[Sequence[str]], numeric: range) -> list[str]:
    align = ["---:" if i in numeric else "---" for i in range(len(header))]
    escape = lambda c: str(c).replace("|", "\\|")  # noqa: E731
    lines = ["| " + " | ".join(escape(h) for h in header) + " |", "| " + " | ".join(align) + " |"]
    lines += ["| " + " | ".join(escape(c) for c in row) + " |" for row in rows]
    return lines


# ------------------------------------------------------------------ report
def _report_parts(report: Report, lang: str, top: int):
    header = [t(lang, "hdr_field"), t(lang, "hdr_type"), "TP", "FP", "FN",
              t(lang, "hdr_precision"), t(lang, "hdr_recall"), "F1", t(lang, "hdr_errors")]
    rows = []
    for path, s in report.fields.items():
        rows.append([path, s.type or "-", s.counts.tp, s.counts.fp, s.counts.fn,
                     _num(s.precision, lang), _num(s.recall, lang), _num(s.f1, lang), _errors(s)])
    m = report.micro
    rows.append([t(lang, "row_micro"), "", m.counts.tp, m.counts.fp, m.counts.fn,
                 _num(m.precision, lang), _num(m.recall, lang), _num(m.f1, lang), ""])
    # the overall error breakdown goes in a note: a long cell in the table would widen the Errors column and wrap
    notes: list[str] = [t(lang, "line_macro", value=_num(report.macro_f1, lang)),
                        t(lang, "line_errors_total", value=_errors(m))]
    if report.skipped:
        notes.append(t(lang, "line_skipped", fields=", ".join(report.skipped)))
    if report.parse_failures:
        notes.append(t(lang, "line_parse_failures", n=report.parse_failures, ids=", ".join(report.parse_failure_ids)))
    if report.extra_docs:
        notes.append(t(lang, "line_extra_docs", ids=", ".join(report.extra_docs)))
    for path, n in report.large_lists.items():
        notes.append(t(lang, "line_large_list", path=path, n=n))
    tops = [t(lang, "row_top_doc", id=d.id, n=d.error_count) for d in report.top_docs(top)]
    return header, rows, notes, tops


def report_text(report: Report, lang: str = "en", top: int = 5, gate: Sequence[GateFailure] | None = None, gated: bool = False) -> str:
    """Terminal table."""
    header, rows, notes, tops = _report_parts(report, lang, top)
    lines = [title_score(lang, len(report.docs)), ""]
    lines += _table(header, rows, range(2, 8))
    lines += ["", *notes]
    if tops:
        lines += ["", t(lang, "line_top_docs"), *[f"  {x}" for x in tops]]
    lines += ["", t(lang, "line_legend")]
    if gated:
        lines += ["", *_gate_lines(gate or [], lang)]
    return "\n".join(lines) + "\n"


def report_markdown(report: Report, lang: str = "en", top: int = 5, gate: Sequence[GateFailure] | None = None, gated: bool = False) -> str:
    """Markdown report (GitHub renders the table; paste it into a job summary)."""
    header, rows, notes, tops = _report_parts(report, lang, top)
    lines = [f"## {title_score(lang, len(report.docs))}", ""]
    lines += _md_table(header, rows, range(2, 8))
    lines += [""] + [f"- {n}" for n in notes]
    if tops:
        lines += ["", f"**{t(lang, 'line_top_docs')}**", ""] + [f"- {x}" for x in tops]
    lines += ["", f"> {t(lang, 'line_legend')}"]
    if gated:
        lines += ["", f"### {t(lang, 'gate_title')}", ""] + [f"- {x}" for x in _gate_lines(gate or [], lang)]
    return "\n".join(lines) + "\n"


def _gate_lines(failures: Sequence[GateFailure], lang: str) -> list[str]:
    lines = [t(lang, "gate_fail_line", path=f.path, f1=f"{f.f1:.3f}", minimum=f"{f.minimum:.3f}") for f in failures]
    lines.append(t(lang, "gate_fail", n=len(failures)) if failures else t(lang, "gate_pass"))
    return lines


# ------------------------------------------------------------------ diff
_STATUS_KEY = {"improved": "status_improved", "regressed": "status_regressed", "same": "status_same"}


def _diff_parts(d: Diff, lang: str):
    header = [t(lang, "hdr_field"), t(lang, "hdr_type"), t(lang, "hdr_f1_a"), t(lang, "hdr_f1_b"),
              t(lang, "hdr_change"), t(lang, "hdr_status")]
    rows = [[p, x.type or "-", _num(x.f1_a, lang), _num(x.f1_b, lang), f"{x.delta:+.3f}", t(lang, _STATUS_KEY[x.status])]
            for p, x in d.fields.items()]
    notes = [t(lang, "line_micro_diff", a=_num(d.micro_a.f1, lang), b=_num(d.micro_b.f1, lang))]
    if any(d.parse_failures):
        notes.append(t(lang, "line_parse_diff", a=d.parse_failures[0], b=d.parse_failures[1]))
    notes.append(t(lang, "line_regressions", n=len(d.regressions), fields=", ".join(d.regressions)) if d.regressions
                 else t(lang, "line_no_regressions"))
    words = {"correct": t(lang, "flip_correct"), "wrong": t(lang, "flip_wrong")}
    flips = [t(lang, "row_flip", doc=f.doc, path=f.path, frm=words[f.direction.split("->")[0]], to=words[f.direction.split("->")[1]])
             for f in d.flips]
    return header, rows, notes, flips


def diff_text(d: Diff, lang: str = "en") -> str:
    header, rows, notes, flips = _diff_parts(d, lang)
    lines = [title_diff(lang, d.documents), ""]
    lines += _table(header, rows, range(2, 5))
    lines += ["", *notes, ""]
    lines += [t(lang, "line_flips"), *[f"  {x}" for x in flips]] if flips else [t(lang, "line_no_flips")]
    return "\n".join(lines) + "\n"


def diff_markdown(d: Diff, lang: str = "en") -> str:
    header, rows, notes, flips = _diff_parts(d, lang)
    lines = [f"## {title_diff(lang, d.documents)}", ""]
    lines += _md_table(header, rows, range(2, 5))
    lines += [""] + [f"- {n}" for n in notes] + [""]
    lines += [f"**{t(lang, 'line_flips')}**", ""] + [f"- {x}" for x in flips] if flips else [t(lang, "line_no_flips")]
    return "\n".join(lines) + "\n"
