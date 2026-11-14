from __future__ import annotations

from extractscore import Config, Counts, FieldRule, evaluate
from extractscore.metrics import FieldStats, macro_f1


def test_hallucination_only_field():
    report = evaluate([{"id": "d", "a": 1}], [{"id": "d", "a": 1, "extra": "x"}])
    stats = report.fields["extra"]
    assert stats.precision == 0.0
    assert stats.recall is None
    assert stats.f1 == 0.0


def test_macro_excludes_none():
    stats = [FieldStats("a", counts=Counts(tp=1)), FieldStats("b", counts=Counts()), FieldStats("c", counts=Counts(fp=1))]
    assert stats[1].f1 is None
    assert macro_f1(stats) == 0.5  # mean of 1.0 and 0.0, the empty field is left out
    assert macro_f1([FieldStats("b")]) is None


def test_ignored_fields_are_skipped():
    config = Config(fields={"notes": FieldRule(ignore=True)})
    report = evaluate([{"id": "d", "a": 1, "notes": "gold text"}], [{"id": "d", "a": 1, "notes": "other"}], config)
    assert report.skipped == ["notes"]
    assert "notes" not in report.fields
    assert report.micro.counts.tp == 1 and report.micro.counts.fp == report.micro.counts.fn == 0


def test_ignored_subtree_and_list_field():
    config = Config(fields={"vendor": FieldRule(ignore=True), "items[].price": FieldRule(ignore=True)})
    gold = [{"id": "d", "vendor": {"n": 1}, "items": [{"q": 1, "price": 5}]}]
    pred = [{"id": "d", "vendor": {"n": 2}, "items": [{"q": 1, "price": 9}]}]
    report = evaluate(gold, pred, config)
    assert list(report.fields) == ["items[].q"]
    assert report.skipped == ["items[].price", "vendor"]


def test_both_empty_field_is_absent():
    report = evaluate([{"id": "d", "a": 1, "b": ""}], [{"id": "d", "a": 1, "b": None}])
    assert list(report.fields) == ["a"]


def test_counts_to_dict_keeps_raw_numbers_for_recomputing():
    report = evaluate([{"id": "d", "a": 1}], [{"id": "d", "a": 2}])
    data = report.to_dict()
    assert data["fields"]["a"]["tp"] == 0 and data["fields"]["a"]["fp"] == 1 and data["fields"]["a"]["fn"] == 1
    assert data["fields"]["a"]["errors"] == {"wrong_value": 1}
    assert {"fields", "micro", "macro_f1", "parse_failures"} <= set(data)
