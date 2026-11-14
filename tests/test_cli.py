from __future__ import annotations

import json

import pytest

from extractscore.cli import main


@pytest.fixture
def sample_args(sample_dir):
    g, a, b, c = (str(sample_dir / n) for n in ("gold.jsonl", "pred_a.jsonl", "pred_b.jsonl", "fields.toml"))
    return g, a, b, c


def test_score_gate_and_formats(sample_args, capsys, tmp_path):
    gold, pred_a, _, config = sample_args
    base = ["score", gold, pred_a, "--config", config, "--lang", "en"]

    assert main([*base, "--min-f1", "0.95"]) == 1
    out = capsys.readouterr().out
    assert "line_items[].qty" in out and "FAIL" in out

    assert main(base) == 0  # no gate, no failure
    assert "FAIL" not in capsys.readouterr().out

    assert main([*base, "--min-f1", "0.95", "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert {"fields", "micro", "macro_f1", "parse_failures"} <= set(data)
    assert data["gate"]["passed"] is False
    assert any(f["field"] == "line_items[].qty" for f in data["gate"]["failures"])

    assert main([*base, "--format", "md"]) == 0
    md = capsys.readouterr().out
    assert md.lstrip().startswith("## ") and "| Field |" in md

    assert main(["score", "/no/such/gold.jsonl", pred_a, "--lang", "en"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: Cannot read") and err.count("\n") == 1 and "Traceback" not in err

    report_file = tmp_path / "report.md"
    assert main([*base, "--format", "md", "--out", str(report_file), "--min-f1", "0.95"]) == 1
    assert "line_items[].qty" in report_file.read_text(encoding="utf-8")
    assert "Wrote" in capsys.readouterr().out


def test_field_min_and_errors(sample_args, capsys):
    gold, pred_a, _, config = sample_args
    base = ["score", gold, pred_a, "--config", config, "--lang", "en"]
    assert main([*base, "--field-min", "date=1.0"]) == 0
    assert main([*base, "--field-min", "total=0.99"]) == 1
    assert main([*base, "--field-min", "nope=0.5"]) == 2
    assert "not in the report" in capsys.readouterr().err
    assert main([*base, "--field-min", "total"]) == 2
    assert main([*base, "--min-f1", "7"]) == 2
    assert main(["score", gold, pred_a, "--config", "/no/such.toml", "--lang", "en"]) == 2
    assert "Cannot read config file" in capsys.readouterr().err


def test_diff_exit_codes(sample_args, capsys):
    gold, a, b, config = sample_args
    base = ["diff", gold, a, b, "--config", config, "--lang", "en"]
    assert main([*base, "--fail-on-regression"]) == 1
    out = capsys.readouterr().out
    rows = {line.split()[0]: line for line in out.splitlines() if line.startswith(("date", "invoice_no", "vendor.tax_id", "line_items[].qty"))}
    assert rows["line_items[].qty"].endswith("improved") and rows["vendor.tax_id"].endswith("improved")
    assert rows["date"].endswith("REGRESSED") and rows["invoice_no"].endswith("REGRESSED")
    assert "inv-003  date: correct -> wrong" in out

    assert main(base) == 0
    capsys.readouterr()
    assert main([*base, "--fail-on-regression", "--tolerance", "1.0"]) == 0
    capsys.readouterr()
    assert main([*base, "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["regressions"]
    assert main(["diff", gold, a, a, "--config", config, "--fail-on-regression", "--lang", "en"]) == 0


def test_demo_and_export(capsys, tmp_path):
    assert main(["demo", "--lang", "en"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("Practice mock")
    assert "line_items[].qty" in out and "REGRESSED" in out

    target = tmp_path / "practice"
    assert main(["demo", "--export", str(target), "--lang", "en"]) == 0
    assert (target / "gold.jsonl").exists() and (target / "docs" / "inv-001.txt").exists()
    capsys.readouterr()
    assert main(["score", str(target / "gold.jsonl"), str(target / "pred_a.jsonl"), "--config", str(target / "fields.toml"), "--lang", "en"]) == 0
    capsys.readouterr()
    assert main(["demo", "--export", str(target), "--lang", "en"]) == 2  # refuses to overwrite
    assert "already exists" in capsys.readouterr().err


def test_version_and_missing_command(capsys):
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0 and "extractscore 0.1.2" in capsys.readouterr().out
    with pytest.raises(SystemExit) as info:
        main([])
    assert info.value.code == 2
