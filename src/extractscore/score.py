"""Scoring: walk a gold document and a predicted document side by side.

Every leaf value of the gold document becomes a scoring event for its *field path*
(``vendor.name``, ``line_items[].qty``).  Lists of objects are paired first
(see :mod:`extractscore.align`), then scored field by field.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .align import match_items
from .compare import MATCH, TYPE_ERROR, compare_values, is_empty
from .config import Config
from .errors import InputError
from .io import ParseFailure, load_jsonl
from .metrics import Counts, FieldStats, macro_f1

_BIG_LIST = 500  # alignment is O(n^3); warn above this many unmatched items


# ---------------------------------------------------------------- sinks
class _Recorder:
    """Collects events per field path for one document."""

    def __init__(self) -> None:
        self.fields: dict[str, FieldStats] = {}

    def add(self, path: str, kind: str, type_: str | None) -> None:
        stats = self.fields.get(path)
        if stats is None:
            stats = self.fields[path] = FieldStats(path=path, type=type_)
        elif stats.type is None:
            stats.type = type_
        stats.counts.add_event(kind)


class _Counter:
    """Cheap sink used only to measure how similar two list items are."""

    def __init__(self) -> None:
        self.tp = self.fp = self.fn = 0

    def add(self, path: str, kind: str, type_: str | None) -> None:
        if kind == "tp":
            self.tp += 1
        elif kind in ("wrong_value", "type_error"):
            self.fp += 1
            self.fn += 1
        elif kind == "hallucinated":
            self.fp += 1
        else:
            self.fn += 1


@dataclass
class _Ctx:
    config: Config
    sink: Any
    miss_kind: str = "missing"
    large_lists: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------- walking
def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _norm(value: Any, ctx: _Ctx) -> Any:
    return None if is_empty(value, ctx.config.empty_as_null) else value


def _walk(gold: Any, pred: Any, path: str, ctx: _Ctx) -> None:
    config = ctx.config
    explicit = config.fields.get(path)
    if explicit is not None and explicit.ignore:
        return
    gold, pred = _norm(gold, ctx), _norm(pred, ctx)
    if gold is None and pred is None:
        return

    # objects
    if isinstance(gold, dict) or (gold is None and isinstance(pred, dict)):
        if pred is not None and not isinstance(pred, dict):
            ctx.sink.add(path, "hallucinated", "text")  # a scalar/list where an object was expected
        _walk_object(gold if isinstance(gold, dict) else {}, pred if isinstance(pred, dict) else {}, path, ctx)
        return

    # lists
    if isinstance(gold, list) or (gold is None and isinstance(pred, list)):
        gold_items = gold if isinstance(gold, list) else []
        if pred is None:
            pred_items: list = []
        elif isinstance(pred, list):
            pred_items = pred
        else:
            pred_items = [pred]  # a single value where a list was expected counts as a one-item list
        _walk_list(gold_items, pred_items, path + "[]", ctx)
        return

    # scalars
    if gold is None:
        ctx.sink.add(path, "hallucinated", config.rule_for(path, pred).type)
        return
    rule = config.rule_for(path, gold)
    if pred is None:
        ctx.sink.add(path, ctx.miss_kind, rule.type)
        return
    outcome = compare_values(rule, gold, pred, config.date_formats)
    kind = "tp" if outcome == MATCH else "type_error" if outcome == TYPE_ERROR else "wrong_value"
    ctx.sink.add(path, kind, rule.type)


def _walk_object(gold: dict, pred: dict, path: str, ctx: _Ctx) -> None:
    for key in gold:
        _walk(gold[key], pred.get(key), _join(path, key), ctx)
    for key in pred:
        if key not in gold:
            _walk(None, pred[key], _join(path, key), ctx)


def _walk_list(gold: list, pred: list, path: str, ctx: _Ctx) -> None:
    explicit = ctx.config.fields.get(path)
    if explicit is not None and explicit.ignore:
        return
    gold = [x for x in gold if not is_empty(x, ctx.config.empty_as_null)]
    pred = [x for x in pred if not is_empty(x, ctx.config.empty_as_null)]
    if any(isinstance(x, dict) for x in gold + pred):
        _walk_object_list(gold, pred, path, ctx)
    else:
        _walk_scalar_list(gold, pred, path, ctx)


def _walk_object_list(gold: list, pred: list, path: str, ctx: _Ctx) -> None:
    gold_objs = [x for x in gold if isinstance(x, dict)]
    pred_objs = [x for x in pred if isinstance(x, dict)]
    for _ in [x for x in gold if not isinstance(x, dict)]:
        ctx.sink.add(path, ctx.miss_kind, "text")
    for _ in [x for x in pred if not isinstance(x, dict)]:
        ctx.sink.add(path, "hallucinated", "text")

    def similarity(g: dict, p: dict) -> float:
        counter = _Counter()
        sub = _Ctx(ctx.config, counter)
        _walk_object(g, p, path, sub)
        denominator = max(counter.tp + counter.fn, counter.tp + counter.fp)
        return counter.tp / denominator if denominator else 0.0

    pairs, lone_gold, lone_pred = match_items(gold_objs, pred_objs, similarity, ctx.config.match_threshold)
    if max(len(lone_gold), len(lone_pred)) > _BIG_LIST:
        ctx.large_lists[path] = max(ctx.large_lists.get(path, 0), max(len(lone_gold), len(lone_pred)))
    for i, j in pairs:
        _walk_object(gold_objs[i], pred_objs[j], path, ctx)
    for i in lone_gold:
        _walk_object(gold_objs[i], {}, path, ctx)
    for j in lone_pred:
        _walk_object({}, pred_objs[j], path, ctx)


def _walk_scalar_list(gold: list, pred: list, path: str, ctx: _Ctx) -> None:
    config = ctx.config
    if not gold and not pred:
        return
    rule = config.rule_for(path, gold[0] if gold else pred[0])
    unused = list(range(len(pred)))
    lone_gold = 0
    for g in gold:
        for position, j in enumerate(unused):
            if compare_values(rule, g, pred[j], config.date_formats) == MATCH:
                del unused[position]
                ctx.sink.add(path, "tp", rule.type)
                break
        else:
            lone_gold += 1
    for _ in range(lone_gold):
        ctx.sink.add(path, ctx.miss_kind, rule.type)
    for _ in unused:
        ctx.sink.add(path, "hallucinated", rule.type)


# ---------------------------------------------------------------- results
@dataclass
class DocResult:
    """Scoring result of one document."""

    id: str | None
    fields: dict[str, FieldStats]
    parse_failure: bool = False
    large_lists: dict[str, int] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(s.counts.error_count for s in self.fields.values())


@dataclass
class Report:
    """Dataset-level result: per-field stats, micro/macro aggregates, bookkeeping."""

    fields: dict[str, FieldStats]
    micro: FieldStats
    macro_f1: float | None
    docs: list[DocResult]
    parse_failures: int
    parse_failure_ids: list[str]
    skipped: list[str]
    extra_docs: list[str] = field(default_factory=list)
    large_lists: dict[str, int] = field(default_factory=dict)

    @property
    def doc_ids(self) -> list[str]:
        return [d.id for d in self.docs if d.id is not None]

    def top_docs(self, n: int = 5) -> list[DocResult]:
        """Documents with the most error events (ties keep file order), at most ``n``."""
        ranked = sorted((d for d in self.docs if d.error_count), key=lambda d: -d.error_count)
        return ranked[: max(n, 0)]

    def to_dict(self, top: int = 5) -> dict[str, Any]:
        """JSON-ready dict.  Keys are English regardless of the display language."""
        return {
            "fields": {path: stats.to_dict() for path, stats in self.fields.items()},
            "micro": self.micro.counts.to_dict(),
            "macro_f1": self.macro_f1,
            "documents": len(self.docs),
            "parse_failures": self.parse_failures,
            "parse_failure_ids": list(self.parse_failure_ids),
            "skipped": list(self.skipped),
            "extra_docs": list(self.extra_docs),
            "top_docs": [{"id": d.id, "errors": d.error_count} for d in self.top_docs(top)],
        }

    def to_markdown(self, lang: str = "en", top: int = 5) -> str:
        from .render import report_markdown

        return report_markdown(self, lang, top)


def compare(gold: Mapping[str, Any], pred: Mapping[str, Any] | ParseFailure | None, config: Config | None = None) -> DocResult:
    """Score one document.  A missing or broken prediction scores every gold field as a failure."""
    config = config or Config()
    recorder = _Recorder()
    failed = not isinstance(pred, Mapping)
    ctx = _Ctx(config, recorder, miss_kind="parse_failure" if failed else "missing")
    _walk_object(dict(gold), {} if failed else dict(pred), "", ctx)  # type: ignore[arg-type]
    return DocResult(id=None, fields=recorder.fields, parse_failure=failed, large_lists=ctx.large_lists)


def evaluate(gold: Any, pred: Any, config: Config | None = None, *, id_key: str = "id") -> Report:
    """Score a whole dataset.

    ``gold`` and ``pred`` are either iterables of dicts that carry ``id_key`` or
    ``{id: dict}`` mappings.  Predicted values may be :class:`ParseFailure` objects.
    Gold problems raise :class:`InputError`; prediction problems are scored.
    """
    config = config or Config()
    gold_docs = _index(gold, id_key, strict=True)
    pred_docs = _index(pred, id_key, strict=False)
    if not gold_docs:
        raise InputError("err_no_gold")

    totals: dict[str, FieldStats] = {}
    results: list[DocResult] = []
    failed_ids: list[str] = []
    large: dict[str, int] = {}
    for doc_id, gold_doc in gold_docs.items():
        result = compare(_without(gold_doc, id_key), _without(pred_docs.get(doc_id), id_key), config)
        result.id = doc_id
        results.append(result)
        if result.parse_failure:
            failed_ids.append(doc_id)
        for path, stats in result.fields.items():
            total = totals.setdefault(path, FieldStats(path=path, type=stats.type))
            if total.type is None:
                total.type = stats.type
            total.counts.merge(stats.counts)
        for path, size in result.large_lists.items():
            large[path] = max(large.get(path, 0), size)

    fields = dict(sorted(totals.items()))
    micro = FieldStats(path="(micro)")
    for stats in fields.values():
        micro.counts.merge(stats.counts)
    return Report(
        fields=fields,
        micro=micro,
        macro_f1=macro_f1(list(fields.values())),
        docs=results,
        parse_failures=len(failed_ids),
        parse_failure_ids=failed_ids,
        skipped=config.ignored_paths(),
        extra_docs=sorted(set(pred_docs) - set(gold_docs)),
        large_lists=large,
    )


def evaluate_files(gold_path: str | Path, pred_path: str | Path, config: Config | None = None, *, id_key: str = "id") -> Report:
    """Read two JSONL files and :func:`evaluate` them."""
    gold = load_jsonl(gold_path, strict=True, id_key=id_key)
    pred = load_jsonl(pred_path, strict=False, id_key=id_key)
    return evaluate(gold, pred, config, id_key=id_key)


# ---------------------------------------------------------------- helpers
def _index(rows: Any, id_key: str, *, strict: bool) -> dict[str, Any]:
    """Normalise the two accepted input shapes to ``{id: document}``."""
    if isinstance(rows, Mapping):
        return {str(k): v for k, v in rows.items()}
    indexed: dict[str, Any] = {}
    if not isinstance(rows, Iterable):
        raise InputError("err_not_iterable")
    for number, row in enumerate(rows, 1):
        if isinstance(row, ParseFailure):
            if row.doc_id is not None:
                indexed[str(row.doc_id)] = row
            continue
        if not isinstance(row, Mapping) or row.get(id_key) in (None, ""):
            if strict:
                raise InputError("err_missing_id", path="<gold rows>", line=number, id_key=id_key)
            continue
        doc_id = str(row[id_key])
        if strict and doc_id in indexed:
            raise InputError("err_duplicate_id", doc_id=doc_id, line=number)
        indexed[doc_id] = row
    return indexed


def _without(doc: Any, id_key: str) -> Any:
    if isinstance(doc, Mapping):
        return {k: v for k, v in doc.items() if k != id_key}
    return doc
