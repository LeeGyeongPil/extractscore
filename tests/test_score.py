from __future__ import annotations

import pytest

from extractscore import Config, evaluate, evaluate_files


def test_invoice_fixture_per_field_counts(gold_invoice, pred_invoice):
    report = evaluate([gold_invoice], [pred_invoice])
    f = report.fields

    qty = f["line_items[].qty"].counts
    assert (qty.tp, qty.fp, qty.fn) == (2, 1, 1)
    assert qty.errors["wrong_value"] == 1

    tax = f["vendor.tax_id"].counts
    assert (tax.tp, tax.fp, tax.fn) == (0, 0, 1)
    assert tax.errors["missing"] == 1

    discount = f["discount"].counts
    assert (discount.tp, discount.fp, discount.fn) == (0, 1, 0)
    assert discount.errors["hallucinated"] == 1

    for path in ("total", "date", "vendor.name", "line_items[].desc", "line_items[].price", "invoice_no"):
        c = f[path].counts
        assert (c.tp, c.fp, c.fn) == (1 if "[]" not in path else 3, 0, 0), path

    micro = report.micro
    assert round(micro.precision, 3) == round(micro.recall, 3) == round(micro.f1, 3) == 0.857


def test_document_error_ranking_and_ids(gold_invoice, pred_invoice):
    clean = dict(gold_invoice, id="inv-2")
    report = evaluate([gold_invoice, clean], [pred_invoice, clean])
    assert [d.id for d in report.docs] == ["inv-1", "inv-2"]
    assert [d.id for d in report.top_docs()] == ["inv-1"]
    assert report.top_docs()[0].error_count == 3


def test_mapping_inputs_and_id_key(gold_invoice, pred_invoice):
    gold = {"a": {k: v for k, v in gold_invoice.items() if k != "id"}}
    pred = {"a": {k: v for k, v in pred_invoice.items() if k != "id"}}
    assert evaluate(gold, pred).micro.counts.tp == 12
    rows = [{"doc": "x", "total": 5}]
    assert evaluate(rows, [{"doc": "x", "total": "5.00"}], id_key="doc").micro.counts.tp == 1


def test_nested_lists_recurse():
    gold = [{"id": "d", "orders": [{"sku": "A", "tags": [{"k": "x"}, {"k": "y"}]}]}]
    pred = [{"id": "d", "orders": [{"sku": "A", "tags": [{"k": "y"}, {"k": "x"}]}]}]
    report = evaluate(gold, pred)
    assert report.fields["orders[].tags[].k"].counts.tp == 2
    assert report.micro.f1 == 1.0


def test_object_where_scalar_expected_and_scalar_where_object_expected():
    gold = [{"id": "d", "vendor": {"name": "Acme", "tax": "1"}, "n": 1}]
    pred = [{"id": "d", "vendor": "Acme", "n": 1}]
    report = evaluate(gold, pred)
    assert report.fields["vendor.name"].counts.errors["missing"] == 1
    assert report.fields["vendor"].counts.errors["hallucinated"] == 1


def test_sample_runs_match_the_documented_lessons(sample_dir):
    config = Config.from_file(sample_dir / "fields.toml")
    a = evaluate_files(sample_dir / "gold.jsonl", sample_dir / "pred_a.jsonl", config)
    assert a.fields["invoice_no"].counts.errors["wrong_value"] == 1  # INV-215 vs INV-0215: ids are exact
    assert a.fields["total"].counts.errors["type_error"] == 1
    assert a.fields["vendor.tax_id"].counts.errors["missing"] == 2
    assert a.fields["discount"].counts.errors["hallucinated"] == 1
    assert a.fields["date"].f1 == 1.0  # three date formats normalised
    assert a.skipped == ["notes"]
    assert a.parse_failures == 0
    b = evaluate_files(sample_dir / "gold.jsonl", sample_dir / "pred_b.jsonl", config)
    assert b.parse_failures == 1 and b.parse_failure_ids == ["rcp-003"]


@pytest.mark.parametrize("empty", ["", [], {}, None])
def test_empty_values_equal_null(empty):
    report = evaluate([{"id": "d", "a": "x", "b": empty}], [{"id": "d", "a": "x", "b": None}])
    assert "b" not in report.fields
