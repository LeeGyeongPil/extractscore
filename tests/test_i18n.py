from __future__ import annotations

import json
import string

import pytest

from extractscore.cli import main
from extractscore.i18n import MESSAGES, resolve_lang, t


def test_lang_precedence():
    env = {"EXTRACTSCORE_LANG": "ko", "LC_ALL": "en_US.UTF-8", "LANG": "en_US.UTF-8"}
    assert resolve_lang("en", env) == "en"  # --lang wins
    assert resolve_lang(None, env) == "ko"  # then EXTRACTSCORE_LANG
    assert resolve_lang(None, {"LC_ALL": "ko_KR.UTF-8", "LANG": "en_US.UTF-8"}) == "ko"
    assert resolve_lang(None, {"LC_MESSAGES": "ko_KR.UTF-8", "LANG": "en_US.UTF-8"}) == "ko"
    assert resolve_lang(None, {"LANG": "ko_KR.UTF-8"}) == "ko"
    assert resolve_lang(None, {"LANG": "fr_FR.UTF-8"}) == "en"
    assert resolve_lang(None, {"EXTRACTSCORE_LANG": "fr", "LANG": "ko_KR.UTF-8"}) == "en"  # explicit choice wins, not Korean -> English
    assert resolve_lang(None, {}) == "en"


def test_message_keys_match():
    assert set(MESSAGES["en"]) == set(MESSAGES["ko"])
    for key in MESSAGES["en"]:
        fields = lambda s: {f for _, f, _, _ in string.Formatter().parse(s) if f}  # noqa: E731
        assert fields(MESSAGES["en"][key]) == fields(MESSAGES["ko"][key]), key  # same placeholders
        assert MESSAGES["ko"][key].strip() and MESSAGES["en"][key].strip()


def test_unknown_language_falls_back_to_english():
    assert t("fr", "na") == "n/a"


def test_help_in_both_languages(capsys):
    with pytest.raises(SystemExit):
        main(["--help", "--lang", "ko"])
    assert "정답" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--help", "--lang", "en"])
    assert "gold" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["score", "--help", "--lang", "ko"])
    assert "정답" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["score", "--lang=en", "--help"])
    assert "gold JSONL" in capsys.readouterr().out


def test_env_var_selects_language(monkeypatch, capsys):
    monkeypatch.setenv("EXTRACTSCORE_LANG", "ko")
    assert main(["demo"]) == 0
    assert "연습용 목" in capsys.readouterr().out
    assert main(["demo", "--lang", "en"]) == 0  # the flag beats the environment
    assert "Practice mock" in capsys.readouterr().out


def test_demo_ko_and_json_keys_are_language_independent(capsys, sample_dir):
    assert main(["demo", "--lang", "ko"]) == 0
    out = capsys.readouterr().out
    assert "연습용 목" in out and "필드" in out

    args = ["score", str(sample_dir / "gold.jsonl"), str(sample_dir / "pred_a.jsonl"), "--format", "json"]
    main([*args, "--lang", "en"])
    en = json.loads(capsys.readouterr().out)
    main([*args, "--lang", "ko"])
    ko = json.loads(capsys.readouterr().out)
    assert en == ko


def test_errors_and_markdown_follow_language(capsys, sample_dir):
    assert main(["score", "/no/gold.jsonl", "/no/pred.jsonl", "--lang", "ko"]) == 2
    assert capsys.readouterr().err.startswith("오류: ")
    main(["score", str(sample_dir / "gold.jsonl"), str(sample_dir / "pred_a.jsonl"), "--format", "md", "--lang", "ko"])
    assert "| 필드 |" in capsys.readouterr().out


# ---- Korean output must not leak English sentences (Q-1)
ENGLISH_LEAKS = ("must be", "expected", "show this help", "positional arguments", "usage:", "options:",
                 "is not one of", "is only allowed", "the following arguments", "invalid ", "Cannot ")


def _run_ko(args, capsys):
    code = main([*args, "--lang", "ko"])
    cap = capsys.readouterr()
    return code, cap.out + cap.err


def _assert_korean(text):
    for leak in ENGLISH_LEAKS:
        assert leak not in text, (leak, text)


def test_ko_help_has_no_english_argparse_text(capsys):
    for args in (["--help"], ["score", "--help"], ["diff", "--help"], ["demo", "--help"]):
        with pytest.raises(SystemExit):
            main([*args, "--lang", "ko"])
        _assert_korean(capsys.readouterr().out)


def test_ko_usage_errors_are_korean(capsys):
    for args in (["score"], ["score", "a", "b", "--top", "x"], ["score", "a", "b", "--format", "zz"], ["bogus"]):
        with pytest.raises(SystemExit) as exc:
            main([*args, "--lang", "ko"])
        assert exc.value.code == 2
        _assert_korean(capsys.readouterr().err)


def test_ko_error_details_are_korean(tmp_path, sample_dir, capsys):
    gold = sample_dir / "gold.jsonl"
    bad_gold = tmp_path / "bad.jsonl"
    bad_gold.write_text("[1, 2]\n", encoding="utf-8")
    bad_cfg = tmp_path / "bad.toml"
    bad_cfg.write_text('match_threshold = "x"\n', encoding="utf-8")
    fuzzy_cfg = tmp_path / "fuzzy.toml"
    fuzzy_cfg.write_text('[fields.total]\ntype = "number"\nfuzzy = 0.8\n', encoding="utf-8")
    cases = (
        ["score", str(gold), str(gold), "--min-f1", "2"],
        ["score", str(gold), str(gold), "--field-min", "total"],
        ["score", str(gold), str(gold), "--top", "-1"],
        ["score", str(bad_gold), str(gold)],
        ["score", str(gold), str(gold), "--config", str(bad_cfg)],
        ["score", str(gold), str(gold), "--config", str(fuzzy_cfg)],
        ["diff", str(gold), str(gold), str(gold), "--tolerance", "-1"],
    )
    for args in cases:
        code, text = _run_ko(args, capsys)
        assert code == 2, args
        assert "오류" in text
        _assert_korean(text)


def test_out_write_failure_says_cannot_write(tmp_path, sample_dir, capsys):
    gold = str(sample_dir / "gold.jsonl")
    code = main(["score", gold, gold, "--format", "md", "--out", str(tmp_path / "missing" / "x.md"), "--lang", "en"])
    err = capsys.readouterr().err
    assert code == 2 and "Cannot write" in err and "Cannot read" not in err


def test_score_table_separator_fits_120_columns(sample_dir, capsys):
    assert main(["demo", "--lang", "en"]) == 0
    lines = capsys.readouterr().out.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("Field "))
    table = lines[start:lines.index("", start)]  # header, separator and rows up to the first blank line
    assert max(len(line) for line in table) <= 100
