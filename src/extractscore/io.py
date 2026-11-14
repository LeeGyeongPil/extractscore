"""Reading JSON Lines files.

Gold files are read strictly (a bad line is an ``InputError``).  Prediction files are
read leniently: a broken line becomes a :class:`ParseFailure` and is scored as a
failure for that document instead of stopping the whole evaluation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import InputError
from .i18n import Ref, ref


@dataclass(frozen=True)
class ParseFailure:
    """Marks a prediction that could not be read (invalid JSON line, not an object)."""

    doc_id: str | None = None
    line: int | None = None
    detail: str = ""


def load_jsonl(path: str | Path, *, strict: bool, id_key: str = "id") -> dict[str, dict | ParseFailure]:
    """Read ``{id: document}`` from a JSON Lines file.

    ``strict=True`` (gold): invalid JSON, non-object lines, a missing id or a duplicate
    id raise :class:`InputError`.  ``strict=False`` (predictions): a broken line yields a
    :class:`ParseFailure` stored under the id recovered from the raw text (if any); lines
    whose id cannot be recovered are dropped, so that document is scored as having no
    prediction.  Blank lines are ignored.
    """
    file = Path(path)
    try:
        text = file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError("err_input_file", path=str(file), detail=str(exc)) from exc

    docs: dict[str, dict | ParseFailure] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row: Any = json.loads(raw)
            problem: Ref | str = "" if isinstance(row, dict) else ref("d_not_object", kind=type(row).__name__)
        except ValueError as exc:
            row, problem = None, str(exc)

        if problem:
            if strict:
                raise InputError("err_gold_line", path=str(file), line=number, detail=problem)
            doc_id = _salvage_id(raw, id_key)
            if doc_id is not None:
                docs[doc_id] = ParseFailure(doc_id=doc_id, line=number, detail=str(problem))
            continue

        if id_key not in row or row[id_key] in (None, ""):
            if strict:
                raise InputError("err_missing_id", path=str(file), line=number, id_key=id_key)
            continue
        doc_id = str(row[id_key])
        if strict and doc_id in docs:
            raise InputError("err_duplicate_id", doc_id=doc_id, line=number)
        docs[doc_id] = row
    return docs


def _salvage_id(raw: str, id_key: str) -> str | None:
    """Recover the document id from a truncated JSON line, if it is still readable."""
    pattern = r'"' + re.escape(id_key) + r'"\s*:\s*(?:"([^"]*)"|(-?\d+(?:\.\d+)?))'
    found = re.search(pattern, raw)
    if not found:
        return None
    return found.group(1) if found.group(1) is not None else found.group(2)
