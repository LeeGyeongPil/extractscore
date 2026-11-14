"""Pairing items of a list: pure-Python Hungarian algorithm, no dependencies."""

from __future__ import annotations

import json
from typing import Any, Callable, Sequence

INF = float("inf")


def hungarian(cost: Sequence[Sequence[float]]) -> list[int]:
    """Minimum-cost assignment on a square matrix; returns ``col`` for every ``row``.

    O(n^3) shortest-augmenting-path version.  Fine for the few hundred items a
    document list usually has (200 items take a few tens of milliseconds).
    """
    n = len(cost)
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    owner = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        owner[0] = i
        j0 = 0
        minv = [INF] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = owner[j0], INF, 0
            row = cost[i0 - 1]
            for j in range(1, n + 1):
                if not used[j]:
                    current = row[j - 1] - u[i0] - v[j]
                    if current < minv[j]:
                        minv[j], way[j] = current, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[owner[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if owner[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            owner[j0] = owner[j1]
            j0 = j1
    result = [0] * n
    for j in range(1, n + 1):
        result[owner[j] - 1] = j - 1
    return result


def match_items(
    gold: Sequence[dict],
    pred: Sequence[dict],
    similarity: Callable[[dict, dict], float],
    threshold: float,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Pair gold items with predicted items regardless of order.

    Identical items are paired first (cheap, and optimal).  The rest are paired by
    maximising total similarity.  A pair whose similarity is below ``threshold``
    (or zero) is dropped, so both items stay unmatched - a gold item with nothing
    like it counts as missing and the stray predicted item as hallucinated, instead
    of a misleading "wrong value".

    Returns ``(pairs, unmatched_gold_indices, unmatched_pred_indices)``.
    """
    pairs: list[tuple[int, int]] = []
    pool: dict[str, list[int]] = {}
    for j, item in enumerate(pred):
        pool.setdefault(_key(item), []).append(j)
    rest_gold: list[int] = []
    taken: set[int] = set()
    for i, item in enumerate(gold):
        candidates = pool.get(_key(item))
        if candidates:
            j = candidates.pop(0)
            pairs.append((i, j))
            taken.add(j)
        else:
            rest_gold.append(i)
    rest_pred = [j for j in range(len(pred)) if j not in taken]

    if rest_gold and rest_pred:
        size = max(len(rest_gold), len(rest_pred))
        sims = [[0.0] * size for _ in range(size)]
        for a, i in enumerate(rest_gold):
            for b, j in enumerate(rest_pred):
                sims[a][b] = similarity(gold[i], pred[j])
        assignment = hungarian([[1.0 - s for s in row] for row in sims])
        matched_gold: set[int] = set()
        matched_pred: set[int] = set()
        for a, b in enumerate(assignment):
            if a < len(rest_gold) and b < len(rest_pred):
                s = sims[a][b]
                if s > 0.0 and s >= threshold:
                    pairs.append((rest_gold[a], rest_pred[b]))
                    matched_gold.add(rest_gold[a])
                    matched_pred.add(rest_pred[b])
        rest_gold = [i for i in rest_gold if i not in matched_gold]
        rest_pred = [j for j in rest_pred if j not in matched_pred]
    return sorted(pairs), rest_gold, rest_pred


def _key(item: Any) -> str:
    return json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
