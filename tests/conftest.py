from __future__ import annotations

import copy
from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parent.parent / "src" / "extractscore" / "sample"

GOLD_INVOICE = {
    "id": "inv-1",
    "invoice_no": "INV-0042",
    "date": "2026-11-03",
    "vendor": {"name": "Acme Corp", "tax_id": "123-45-678"},
    "total": 1250.0,
    "line_items": [
        {"desc": "Widget A", "qty": 2, "price": 300.0},
        {"desc": "Widget B", "qty": 1, "price": 450.0},
        {"desc": "Service fee", "qty": 1, "price": 200.0},
    ],
}

# Reordered items, one wrong qty, "1,250.00" total, US date, name case/space,
# null tax_id and a hallucinated key.
PRED_INVOICE = {
    "id": "inv-1",
    "invoice_no": "INV-0042",
    "date": "11/03/2026",
    "vendor": {"name": "ACME  Corp", "tax_id": None},
    "total": "1,250.00",
    "discount": 0,
    "line_items": [
        {"desc": "Service fee", "qty": 1, "price": 200.0},
        {"desc": "Widget A", "qty": 3, "price": 300.0},
        {"desc": "Widget B", "qty": 1, "price": 450.0},
    ],
}


@pytest.fixture
def gold_invoice() -> dict:
    return copy.deepcopy(GOLD_INVOICE)


@pytest.fixture
def pred_invoice() -> dict:
    return copy.deepcopy(PRED_INVOICE)


@pytest.fixture
def sample_dir() -> Path:
    return SAMPLE
