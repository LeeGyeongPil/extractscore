from __future__ import annotations

import pytest

from extractscore import Config, ConfigError, FieldRule, compare
from extractscore.compare import MATCH, TYPE_ERROR, WRONG, compare_values, levenshtein, to_date, to_number
from extractscore.config import DEFAULT_DATE_FORMATS


def _one(config: Config | None, gold, pred, path="f"):
    result = compare({path: gold}, {path: pred}, config)
    return result.fields[path].counts


def test_number_normalisation():
    for value in ("1,250.00", "$1,250", 1250, " 1250 ", "USD 1250", "1250 KRW"):
        assert compare_values(FieldRule(type="number"), 1250.0, value, DEFAULT_DATE_FORMATS) == MATCH, value
    for value in ("₩12,000", "12,000원", "12000"):
        assert compare_values(FieldRule(type="number"), 12000, value, DEFAULT_DATE_FORMATS) == MATCH, value
    assert to_number("₩12,000") == 12000.0
    assert to_number("12,000원") == 12000.0
    assert to_number(True) is None and to_number("N/A") is None and to_number("nan") is None
    assert compare_values(FieldRule(type="number"), 10, 10.5, DEFAULT_DATE_FORMATS) == WRONG
    assert compare_values(FieldRule(type="number", tol=0.6), 10, 10.5, DEFAULT_DATE_FORMATS) == MATCH


def test_date_formats_order():
    default = Config()
    for value in ("2026-11-03", "11/03/2026", "2026년 11월 3일", "Nov 3, 2026", "3 Nov 2026", "2026.11.03"):
        assert _one(default, "2026-11-03", value, "date").tp == 1, value
    european_first = Config(date_formats=("%d/%m/%Y", "%Y-%m-%d"))
    assert to_date("11/03/2026", european_first.date_formats).isoformat() == "2026-03-11"
    # with %d/%m/%Y first, 11/03/2026 is 11 March, so it no longer equals 3 November
    assert _one(european_first, "2026-11-03", "11/03/2026", "date").errors["wrong_value"] == 1
    assert _one(european_first, "2026-03-11", "11/03/2026", "date").tp == 1


def test_id_exact_by_default():
    counts = _one(None, "INV-0042", "INV-042", "invoice_no")
    assert counts.errors["wrong_value"] == 1 and counts.tp == 0
    assert _one(None, "INV-0042", " INV-0042 ", "invoice_no").tp == 1  # only surrounding spaces ignored
    assert _one(None, "INV-0042", "inv-0042", "invoice_no").errors["wrong_value"] == 1  # case matters for ids


def test_fuzzy_only_when_configured():
    gold, pred = "Service fee", "Servise fee"
    assert _one(None, gold, pred, "desc").errors["wrong_value"] == 1
    fuzzy = Config(fields={"desc": FieldRule(type="text", fuzzy=0.85)})
    assert _one(fuzzy, gold, pred, "desc").tp == 1
    assert _one(fuzzy, gold, "Totally different", "desc").errors["wrong_value"] == 1


def test_text_normalisation_and_casefold_switch():
    assert _one(None, "Acme Corp", "  ACME   corp ", "name").tp == 1
    strict = Config(fields={"name": FieldRule(type="text", casefold=False)})
    assert _one(strict, "Acme Corp", "ACME Corp", "name").errors["wrong_value"] == 1


def test_enum_and_bool():
    assert _one(Config(fields={"s": FieldRule(type="enum")}), "paid", "PAID", "s").tp == 1
    assert _one(None, True, "yes", "flag").tp == 1
    assert _one(None, True, "maybe", "flag").errors["type_error"] == 1
    assert _one(None, False, False, "flag").tp == 1


def test_type_inference_from_gold():
    result = compare({"n": 3, "d": "2026-11-03", "invoice_no": "A-1", "name": "x", "ok": True}, {})
    types = {p: s.type for p, s in result.fields.items()}
    assert types == {"n": "number", "d": "date", "invoice_no": "id", "name": "text", "ok": "bool"}


def test_levenshtein():
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3


@pytest.mark.parametrize(
    "rule_kwargs, message",
    [
        ({"type": "nope"}, "not one of"),
        ({"type": "number", "tol": -1}, ">= 0"),
        ({"type": "id", "fuzzy": 0.8}, "only allowed on text"),
        ({"type": "text", "fuzzy": 1.5}, "(0, 1]"),
        ({"type": "text", "tol": 1}, "number fields"),
    ],
)
def test_config_errors_say_how_to_fix(rule_kwargs, message):
    with pytest.raises(ConfigError) as info:
        Config(fields={"f": FieldRule(**rule_kwargs)})
    assert message in str(info.value)


def test_config_from_dict_rejects_unknown_keys_and_loads_toml(tmp_path):
    with pytest.raises(ConfigError, match="Unknown key 'fieldz'"):
        Config.from_dict({"fieldz": {}})
    with pytest.raises(ConfigError, match="Unknown key 'toll'"):
        Config.from_dict({"fields": {"a": {"toll": 1}}})
    path = tmp_path / "c.toml"
    path.write_text('[fields."total"]\ntype = "number"\ntol = 0.01\n', encoding="utf-8")
    assert Config.from_file(path).fields["total"].tol == 0.01
    bad = tmp_path / "bad.toml"
    bad.write_text("not = [valid", encoding="utf-8")
    with pytest.raises(ConfigError, match="Cannot read config file"):
        Config.from_file(bad)
    with pytest.raises(ConfigError, match=".toml or .json"):
        Config.from_file(tmp_path / "c.yaml")
    json_path = tmp_path / "c.json"
    json_path.write_text('{"match_threshold": 0.7, "fields": {"x": {"ignore": true}}}', encoding="utf-8")
    loaded = Config.from_file(json_path)
    assert loaded.match_threshold == 0.7 and loaded.ignored_paths() == ["x"]
    with pytest.raises(ConfigError):
        Config(match_threshold=0)


def test_unreadable_gold_falls_back_to_text_equality():
    config = Config(fields={"d": FieldRule(type="date")})
    assert _one(config, "someday", "someday", "d").tp == 1
    assert compare_values(FieldRule(type="date"), "2026-11-03", {"a": 1}, DEFAULT_DATE_FORMATS) == TYPE_ERROR
