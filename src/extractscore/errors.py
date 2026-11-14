"""Exception types.

Every exception carries a message ``key`` and ``params`` so the CLI can print the
same error in the user's language; ``str(exc)`` is always the English text.
"""

from __future__ import annotations

from typing import Any

from .i18n import Ref, t


class ExtractScoreError(Exception):
    """Base class for every error this library raises on purpose."""

    def __init__(self, key: str, /, **params: Any) -> None:
        self.key = key
        self.params = params
        super().__init__(t("en", key, **params))

    def localized(self, lang: str) -> str:
        """Return the message in ``lang`` (``"en"`` or ``"ko"``)."""
        return t(lang, self.key, **{k: v.localized(lang) if isinstance(v, Ref) else v for k, v in self.params.items()})


class ConfigError(ExtractScoreError):
    """The field-rule configuration is invalid (unknown type, bad TOML, negative tolerance...)."""


class InputError(ExtractScoreError):
    """The gold data (or a file) cannot be read: bad JSON line, missing or duplicate id."""
