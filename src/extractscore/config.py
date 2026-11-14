"""Field-rule configuration (TOML or JSON) and type inference."""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

from .errors import ConfigError
from .i18n import ref

FIELD_TYPES = ("number", "date", "text", "id", "enum", "bool")

DEFAULT_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%m/%d/%Y",
    "%d.%m.%Y",
    "%Y년 %m월 %d일",
    "%b %d, %Y",
    "%d %b %Y",
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID_NAME = re.compile(r"(?:^|[_\-])(?:id|no|number|code)(?:$|[_\-])|(?:Id|No|Number|Code)$", re.IGNORECASE)
_RULE_KEYS = ("type", "tol", "fuzzy", "casefold", "ignore")
_CONFIG_KEYS = ("match_threshold", "date_formats", "empty_as_null", "fields")


@dataclass(frozen=True)
class FieldRule:
    """How one field path is compared.

    ``type=None`` means "infer from the gold value".  ``fuzzy`` (text only) is the
    minimum normalised Levenshtein similarity that still counts as a match.
    """

    type: str | None = None
    tol: float = 0.0
    fuzzy: float | None = None
    casefold: bool | None = None
    ignore: bool = False


@dataclass(frozen=True)
class Config:
    """Scoring configuration.  ``Config()`` is a valid, fully inferred default."""

    fields: Mapping[str, FieldRule] = field(default_factory=dict)
    match_threshold: float = 0.5
    date_formats: tuple[str, ...] = DEFAULT_DATE_FORMATS
    empty_as_null: bool = True

    def __post_init__(self) -> None:
        if not 0.0 < self.match_threshold <= 1.0:
            raise ConfigError("err_config_value", where="match_threshold", detail=ref("d_range_0_1"))
        if not self.date_formats or not all(isinstance(f, str) and f for f in self.date_formats):
            raise ConfigError("err_config_value", where="date_formats", detail=ref("d_date_formats_nonempty"))
        for path, rule in self.fields.items():
            _validate_rule(path, rule)

    # ---- construction -------------------------------------------------
    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Config":
        """Build a config from parsed TOML/JSON data, rejecting unknown keys (typo protection)."""
        if not isinstance(data, Mapping):
            raise ConfigError("err_config_value", where="config", detail=ref("d_top_table"))
        _reject_unknown(data, _CONFIG_KEYS, "config")
        raw_fields = data.get("fields", {})
        if not isinstance(raw_fields, Mapping):
            raise ConfigError("err_config_value", where="fields", detail=ref("d_fields_table"))
        rules: dict[str, FieldRule] = {}
        for path, raw in raw_fields.items():
            if not isinstance(raw, Mapping):
                raise ConfigError("err_config_value", where=f"fields.{path}", detail=ref("d_field_table"))
            _reject_unknown(raw, _RULE_KEYS, f"fields.{path}")
            rules[str(path)] = FieldRule(
                type=raw.get("type"),
                tol=_as_number(raw.get("tol", 0.0), f"fields.{path}.tol"),
                fuzzy=None if raw.get("fuzzy") is None else _as_number(raw["fuzzy"], f"fields.{path}.fuzzy"),
                casefold=raw.get("casefold"),
                ignore=bool(raw.get("ignore", False)),
            )
        kwargs: dict[str, Any] = {"fields": rules}
        if "match_threshold" in data:
            kwargs["match_threshold"] = _as_number(data["match_threshold"], "match_threshold")
        if "date_formats" in data:
            formats = data["date_formats"]
            if not isinstance(formats, (list, tuple)):
                raise ConfigError("err_config_value", where="date_formats", detail=ref("d_date_formats_list"))
            kwargs["date_formats"] = tuple(formats)
        if "empty_as_null" in data:
            kwargs["empty_as_null"] = bool(data["empty_as_null"])
        return cls(**kwargs)

    @classmethod
    def from_file(cls, path: str | Path) -> "Config":
        """Load ``.toml`` or ``.json``."""
        file = Path(path)
        suffix = file.suffix.lower()
        if suffix not in (".json", ".toml"):
            raise ConfigError("err_config_file", path=str(file), detail=ref("d_config_ext"))
        try:
            text = file.read_bytes().decode("utf-8-sig")
            data = json.loads(text) if suffix == ".json" else tomllib.loads(text)
        except (OSError, UnicodeDecodeError, ValueError) as exc:  # tomllib/json errors are ValueError
            raise ConfigError("err_config_file", path=str(file), detail=str(exc)) from exc
        return cls.from_dict(data)

    # ---- lookup -------------------------------------------------------
    def ignored_paths(self) -> list[str]:
        """Configured paths that are not scored."""
        return sorted(p for p, r in self.fields.items() if r.ignore)

    def rule_for(self, path: str, sample: Any) -> FieldRule:
        """Return the rule for ``path`` with ``type`` resolved (explicit, hinted or inferred)."""
        explicit = self.fields.get(path)
        if explicit is not None and explicit.type is not None:
            return explicit
        if explicit is None:
            return FieldRule(type=infer_type(path, sample))
        if explicit.fuzzy is not None:
            return replace(explicit, type="text")
        if explicit.tol > 0:
            return replace(explicit, type="number")
        return replace(explicit, type=infer_type(path, sample))


def infer_type(path: str, sample: Any) -> str:
    """Conservative type inference from a gold value (ids and text stay exact)."""
    if isinstance(sample, bool):
        return "bool"
    if isinstance(sample, (int, float)):
        return "number"
    if isinstance(sample, str):
        if _ISO_DATE.match(sample.strip()):
            return "date"
        leaf = path.rsplit(".", 1)[-1].rstrip("[]")
        if _ID_NAME.search(leaf):
            return "id"
    return "text"


def _validate_rule(path: str, rule: FieldRule) -> None:
    where = f"fields.{path}"
    if rule.type is not None and rule.type not in FIELD_TYPES:
        raise ConfigError("err_config_value", where=f"{where}.type", detail=ref("d_type_unknown", type=repr(rule.type), allowed=", ".join(FIELD_TYPES)))
    if rule.tol < 0:
        raise ConfigError("err_config_value", where=f"{where}.tol", detail=ref("d_tol_negative"))
    if rule.fuzzy is not None:
        if not 0.0 < rule.fuzzy <= 1.0:
            raise ConfigError("err_config_value", where=f"{where}.fuzzy", detail=ref("d_range_0_1"))
        if rule.type not in (None, "text"):
            raise ConfigError(
                "err_config_value",
                where=f"{where}.fuzzy",
                detail=ref("d_fuzzy_text_only", type=repr(rule.type)),
            )
    if rule.tol > 0 and rule.type not in (None, "number"):
        raise ConfigError("err_config_value", where=f"{where}.tol", detail=ref("d_tol_number_only"))


def _reject_unknown(data: Mapping[str, Any], allowed: tuple[str, ...], where: str) -> None:
    for key in data:
        if key not in allowed:
            raise ConfigError("err_config_unknown_key", key=str(key), where=where, allowed=", ".join(allowed))


def _as_number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError("err_config_value", where=where, detail=ref("d_expected_number", value=repr(value)))
    return float(value)
