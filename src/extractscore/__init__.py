"""extractscore - field-level precision/recall/F1 for LLM-extracted JSON."""

from __future__ import annotations

__version__ = "0.1.2"

from .config import Config, FieldRule
from .diff import Diff, FieldDelta, Flip, diff
from .errors import ConfigError, ExtractScoreError, InputError
from .gate import GateFailure, check_gates
from .io import ParseFailure, load_jsonl
from .metrics import Counts, FieldStats
from .score import DocResult, Report, compare, evaluate, evaluate_files

__all__ = [
    "Config",
    "ConfigError",
    "Counts",
    "Diff",
    "DocResult",
    "ExtractScoreError",
    "FieldDelta",
    "FieldRule",
    "FieldStats",
    "Flip",
    "GateFailure",
    "InputError",
    "ParseFailure",
    "Report",
    "__version__",
    "check_gates",
    "compare",
    "diff",
    "evaluate",
    "evaluate_files",
    "load_jsonl",
]
