from __future__ import annotations

import random
import time

from extractscore import Config, compare, evaluate
from extractscore.align import hungarian, match_items


def _items(n: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    return [{"desc": f"item {i} {rng.randint(0, 10**6)}", "qty": rng.randint(1, 9), "price": float(rng.randint(1, 500))} for i in range(n)]


def test_order_independent():
    gold = _items(8)
    pred = list(reversed(gold))
    result = compare({"items": gold}, {"items": pred})
    for path in ("items[].desc", "items[].qty", "items[].price"):
        assert result.fields[path].counts.tp == 8
        assert result.fields[path].counts.fp == result.fields[path].counts.fn == 0


def test_weak_pair_split():
    gold = {"items": [{"desc": "Widget", "qty": 2, "price": 10.0}]}
    pred = {"items": [{"desc": "Gadget", "qty": 9, "price": 99.0}]}  # nothing in common
    result = compare(gold, pred)
    for path in ("items[].desc", "items[].qty", "items[].price"):
        counts = result.fields[path].counts
        assert counts.errors["missing"] == 1 and counts.errors["hallucinated"] == 1, path
        assert counts.errors["wrong_value"] == 0, path


def test_strong_enough_pair_reports_wrong_value():
    gold = {"items": [{"desc": "Widget", "qty": 2, "price": 10.0}]}
    pred = {"items": [{"desc": "Widget", "qty": 3, "price": 10.0}]}
    counts = compare(gold, pred).fields["items[].qty"].counts
    assert counts.errors["wrong_value"] == 1 and counts.errors["missing"] == 0


def test_threshold_is_configurable():
    gold = {"items": [{"a": 1, "b": 2, "c": 3, "d": 4}]}
    pred = {"items": [{"a": 1, "b": 0, "c": 0, "d": 0}]}  # 1 of 4 fields right
    assert compare(gold, pred, Config(match_threshold=0.5)).fields["items[].b"].counts.errors["missing"] == 1
    assert compare(gold, pred, Config(match_threshold=0.25)).fields["items[].b"].counts.errors["wrong_value"] == 1


def test_scalar_list_multiset():
    result = compare({"tags": ["a", "b", "b"]}, {"tags": ["b", "a", "c"]})
    counts = result.fields["tags[]"].counts
    assert (counts.tp, counts.fp, counts.fn) == (2, 1, 1)
    assert counts.errors["missing"] == 1 and counts.errors["hallucinated"] == 1


def test_single_value_where_list_expected_counts_as_one_item():
    counts = compare({"tags": ["a"]}, {"tags": "a"}).fields["tags[]"].counts
    assert counts.tp == 1 and counts.fp == counts.fn == 0


def test_hungarian_finds_the_global_optimum():
    cost = [[4.0, 1.0, 3.0], [2.0, 0.0, 5.0], [3.0, 2.0, 2.0]]
    assignment = hungarian(cost)
    assert sum(cost[i][j] for i, j in enumerate(assignment)) == 5.0
    assert sorted(assignment) == [0, 1, 2]


def test_match_items_pairs_identical_items_first():
    pairs, lone_gold, lone_pred = match_items([{"a": 1}, {"a": 2}], [{"a": 2}, {"a": 1}], lambda g, p: 0.0, 0.5)
    assert pairs == [(0, 1), (1, 0)] and not lone_gold and not lone_pred


def test_200_items_under_1s():
    gold = _items(200)
    rng = random.Random(7)
    pred = [dict(item, qty=item["qty"] + 1) if i % 3 == 0 else dict(item) for i, item in enumerate(gold)]
    rng.shuffle(pred)  # worst case for the cheap path: a third of the items differ
    start = time.perf_counter()
    report = evaluate([{"id": "d", "items": gold}], [{"id": "d", "items": pred}])
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"alignment took {elapsed:.2f}s"
    assert report.fields["items[].qty"].counts.errors["wrong_value"] == 67
    assert report.fields["items[].desc"].counts.tp == 200
