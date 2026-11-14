from __future__ import annotations

import pytest

from extractscore import Config, InputError, diff, evaluate, evaluate_files

GOLD = [{"id": "d1", "a": 1, "b": "x"}, {"id": "d2", "a": 2, "b": "y"}]


def _diff(pred_a, pred_b, **kw):
    return diff(evaluate(GOLD, pred_a), evaluate(GOLD, pred_b), **kw)


def test_improved_regressed_same_and_flips():
    a = [{"id": "d1", "a": 9, "b": "x"}, {"id": "d2", "a": 2, "b": "y"}]
    b = [{"id": "d1", "a": 1, "b": "x"}, {"id": "d2", "a": 2, "b": "WRONG"}]
    d = _diff(a, b)
    assert d.fields["a"].status == "improved"
    assert d.fields["b"].status == "regressed"
    assert d.regressions == ["b"] and d.improvements == ["a"]
    assert [(f.doc, f.path, f.direction) for f in d.flips] == [
        ("d1", "a", "wrong->correct"),
        ("d2", "b", "correct->wrong"),
    ]


def test_identical_runs_are_same():
    pred = [{"id": "d1", "a": 1, "b": "x"}, {"id": "d2", "a": 2, "b": "y"}]
    d = _diff(pred, pred)
    assert {f.status for f in d.fields.values()} == {"same"} and not d.flips


def test_tolerance():
    a = [{"id": "d1", "a": 1, "b": "x"}, {"id": "d2", "a": 2, "b": "y"}]
    b = [{"id": "d1", "a": 1, "b": "x"}, {"id": "d2", "a": 5, "b": "y"}]  # a: F1 1.0 -> 0.5
    assert _diff(a, b).regressions == ["a"]
    assert _diff(a, b, tolerance=0.5).regressions == []  # a drop of exactly 0.5 is allowed
    assert _diff(a, b, tolerance=0.49).regressions == ["a"]
    with pytest.raises(InputError, match="tolerance"):
        _diff(a, b, tolerance=-1)


def test_parse_failure_counts_as_wrong():
    a = [{"id": "d1", "a": 1, "b": "x"}, {"id": "d2", "a": 2, "b": "y"}]
    d = _diff(a, [a[0]])
    assert d.parse_failures == (0, 1)
    assert {(f.doc, f.path) for f in d.flips} == {("d2", "a"), ("d2", "b")}


def test_different_gold_sets_are_rejected():
    other = evaluate([{"id": "zzz", "a": 1}], [{"id": "zzz", "a": 1}])
    with pytest.raises(InputError, match="same gold set"):
        diff(evaluate(GOLD, GOLD), other)


def test_to_dict_and_markdown_languages(sample_dir):
    config = Config.from_file(sample_dir / "fields.toml")
    gold = sample_dir / "gold.jsonl"
    d = diff(evaluate_files(gold, sample_dir / "pred_a.jsonl", config), evaluate_files(gold, sample_dir / "pred_b.jsonl", config))
    data = d.to_dict()
    assert data["fields"]["date"]["status"] == "regressed" and data["fields"]["line_items[].qty"]["status"] == "improved"
    assert "REGRESSED" in d.to_markdown("en") and "후퇴" in d.to_markdown("ko")
    assert {"fields", "flips", "regressions"} <= set(data)
