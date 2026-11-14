# Practice mock

Everything in this folder is made up. The predictions in `pred_a.jsonl` and `pred_b.jsonl` were **written by hand**, not produced by a model; they imitate mistakes LLM extractors typically make. No model is called anywhere in `extractscore demo`.

| File | What it is |
|---|---|
| `docs/*.txt` | Six fictional invoices and receipts (the source text, if you want to try your own extractor) |
| `gold.jsonl` | The correct answer for each document |
| `pred_a.jsonl` | "Existing prompt" run |
| `pred_b.jsonl` | "Prompt v2" run (one line is cut off, like a truncated response) |
| `fields.toml` | Field rules used by the demo |

Mistakes planted in run A, and what `extractscore` does with them:

| Mistake | Where | Result |
|---|---|---|
| Line items in a different order | all documents | paired by content, scored as correct |
| `"1,250.00"`, `"₩48,000"`, `"12,000원"` as text | `total` | normalised as numbers, correct |
| `11/03/2026`, `2026년 10월 21일`, `Nov 4, 2026` | `date` | normalised as dates, correct |
| `ACME  Supplies`, `green leaf cafe` | `vendor.name` | whitespace and case ignored, correct |
| `Note book` for `Notebook` | `line_items[].desc` | fuzzy 0.85 is on for this field, correct |
| `INV-215` for `INV-0215` | `invoice_no` | ids are exact: `wrong_value` |
| a wrong `qty` | `line_items[].qty` | `wrong_value` |
| `tax_id: null` | `vendor.tax_id` | `missing` |
| an extra `discount` key | `discount` | `hallucinated` |
| `"N/A"` where a number belongs | `total` | `type_error` (scored, not an exception) |
| `notes` | `notes` | listed as skipped, never counted as passing |

Run B fixes the quantities and the tax ids, but breaks `date` and `invoice_no` in some documents and has a cut-off last line (`parse_failure`).
