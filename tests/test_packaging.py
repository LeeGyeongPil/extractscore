from __future__ import annotations

import tomllib
from pathlib import Path

import extractscore

ROOT = Path(__file__).resolve().parent.parent


def _project() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def test_no_runtime_dependencies():
    project = _project()
    assert project["dependencies"] == []
    assert project["requires-python"] == ">=3.11"


def test_version_and_entry_point_agree():
    project = _project()
    assert project["version"] == extractscore.__version__
    assert project["scripts"]["extractscore"] == "extractscore.cli:main"
    assert project["license"] == "MIT"


def test_sample_files_ship_with_the_package():
    sample = Path(extractscore.__file__).parent / "sample"
    for name in ("gold.jsonl", "pred_a.jsonl", "pred_b.jsonl", "fields.toml", "README.md"):
        assert (sample / name).is_file(), name
    assert len(list((sample / "docs").glob("*.txt"))) == 6


def test_core_imports_only_the_standard_library():
    source = "\n".join(p.read_text(encoding="utf-8") for p in (Path(extractscore.__file__).parent).glob("*.py"))
    for forbidden in ("import numpy", "import scipy", "import rapidfuzz", "import litellm", "import pydantic"):
        assert forbidden not in source
