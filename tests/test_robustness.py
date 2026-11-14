from __future__ import annotations

import json

import pytest

from extractscore import InputError, ParseFailure, evaluate, evaluate_files, load_jsonl


def test_type_mismatch_is_scored():
    gold = [{"id": "d", "total": 10.0}]
    for bad in ("N/A", {"v": 1}, [1, 2]):
        report = evaluate(gold, [{"id": "d", "total": bad}])
        counts = report.fields["total"].counts
        assert (counts.fp, counts.fn) == (1, 1), bad
        assert counts.errors["type_error"] == 1, bad


def test_parse_failure_line(tmp_path):
    gold = tmp_path / "gold.jsonl"
    pred = tmp_path / "pred.jsonl"
    gold.write_text(
        '{"id": "a", "total": 1, "name": "x"}\n{"id": "b", "total": 2, "name": "y"}\n', encoding="utf-8"
    )
    pred.write_text('{"id": "a", "total": 1, "name": "x"}\n{"id": "b", "total": 2, "na\n', encoding="utf-8")
    report = evaluate_files(gold, pred)
    assert report.parse_failures == 1
    assert report.parse_failure_ids == ["b"]
    counts = report.fields["total"].counts
    assert (counts.tp, counts.fn, counts.fp) == (1, 1, 0)
    assert counts.errors["parse_failure"] == 1
    assert report.fields["name"].counts.errors["parse_failure"] == 1


def test_missing_pred_doc():
    report = evaluate([{"id": "a", "x": 1}, {"id": "b", "x": 2}], [{"id": "a", "x": 1}])
    assert report.parse_failures == 1 and report.parse_failure_ids == ["b"]
    assert report.fields["x"].counts.errors["parse_failure"] == 1


def test_parse_failure_objects_and_extra_docs():
    pred = [ParseFailure(doc_id="a", detail="cut off"), {"id": "zzz", "x": 1}]
    report = evaluate([{"id": "a", "x": 1}], pred)
    assert report.parse_failures == 1 and report.extra_docs == ["zzz"]


def test_unattributable_broken_pred_line_is_dropped(tmp_path):
    pred = tmp_path / "p.jsonl"
    pred.write_text("{broken\n[1, 2]\n\n", encoding="utf-8")
    assert load_jsonl(pred, strict=False) == {}


def test_gold_errors_raise(tmp_path):
    with pytest.raises(InputError, match="Duplicate document id 'a'"):
        evaluate([{"id": "a", "x": 1}, {"id": "a", "x": 2}], [])
    with pytest.raises(InputError, match="missing the 'id' key"):
        evaluate([{"x": 1}], [])
    with pytest.raises(InputError, match="no documents"):
        evaluate([], [])
    bad = tmp_path / "gold.jsonl"
    bad.write_text('{"id": "a"}\n{"id": \n', encoding="utf-8")
    with pytest.raises(InputError, match="line 2"):
        load_jsonl(bad, strict=True)
    not_object = tmp_path / "g2.jsonl"
    not_object.write_text("[1, 2]\n", encoding="utf-8")
    with pytest.raises(InputError, match="expected an object"):
        load_jsonl(not_object, strict=True)
    with pytest.raises(InputError, match="Cannot read"):
        load_jsonl(tmp_path / "nope.jsonl", strict=True)
    dup = tmp_path / "g3.jsonl"
    dup.write_text(json.dumps({"id": "a"}) + "\n" + json.dumps({"id": "a"}) + "\n", encoding="utf-8")
    with pytest.raises(InputError, match="line 2"):
        load_jsonl(dup, strict=True)


def test_error_messages_are_localised():
    try:
        evaluate([], [])
    except InputError as exc:
        assert "정답 세트" in exc.localized("ko")
        assert "gold set" in exc.localized("en")


def test_null_values_never_raise():
    report = evaluate([{"id": "d", "a": None, "b": 1, "c": [None]}], [{"id": "d", "a": None, "b": None, "c": None}])
    assert report.fields["b"].counts.errors["missing"] == 1
    assert "a" not in report.fields and "c[]" not in report.fields


BOM = b"\xef\xbb\xbf"
_GOLD = b'{"id":"a","x":1}\n{"id":"b","x":2}\n'


def test_bom_prediction_file(tmp_path):
    gold = tmp_path / "g.jsonl"
    pred = tmp_path / "p.jsonl"
    gold.write_bytes(_GOLD)
    pred.write_bytes(BOM + _GOLD)
    report = evaluate_files(gold, pred)
    assert report.parse_failures == 0
    counts = report.fields["x"].counts
    assert (counts.tp, counts.fp, counts.fn) == (2, 0, 0)


def test_bom_gold_file(tmp_path):
    from extractscore.cli import main

    gold = tmp_path / "g.jsonl"
    pred = tmp_path / "p.jsonl"
    gold.write_bytes(BOM + _GOLD)
    pred.write_bytes(_GOLD)
    assert main(["--lang", "en", "score", str(gold), str(pred)]) == 0


def test_bom_config_json_and_toml(tmp_path):
    from extractscore.cli import main

    gold = tmp_path / "g.jsonl"
    gold.write_bytes(_GOLD)
    cj = tmp_path / "c.json"
    cj.write_bytes(BOM + b'{"fields":{}}')
    ct = tmp_path / "c.toml"
    ct.write_bytes(BOM + b'[fields.x]\ntype = "number"\n')
    for cfg in (cj, ct):
        assert main(["--lang", "en", "score", str(gold), str(gold), "--config", str(cfg)]) == 0
