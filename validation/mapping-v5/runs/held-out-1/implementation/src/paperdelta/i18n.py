"""Language-independent messages with explicit, isolated presentation contexts.

Message is a string whose canonical value is English. JSON, fingerprints and old
record contracts therefore remain language independent. Live renderers retain
the message key and arguments and select a language only when showing text.
"""

from __future__ import annotations

import json
import locale
import os
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from importlib.resources import files
from string import Formatter
from typing import Any

LANGUAGES = ("en", "zh-CN")
_language: ContextVar[str] = ContextVar("paperdelta_language", default="en")


@lru_cache(maxsize=2)
def catalog(language: str) -> dict[str, str]:
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")
    return json.loads(
        files("paperdelta").joinpath("locales", language + ".json").read_text("utf-8")
    )


def normalize_language(value: str) -> str | None:
    value = value.replace("_", "-").split(".", 1)[0].lower()
    if value == "zh" or value in {"zh-cn", "zh-hans", "zh-sg", "chinese-china"}:
        return "zh-CN"
    if value.startswith("chinese (simplified)"):
        return "zh-CN"
    if value == "en" or value.startswith("en-") or value.startswith("english"):
        return "en"
    return None


def resolve_language(
    requested: str | None = None,
    *,
    preferences: dict | None = None,
    environ: dict | None = None,
    system_locale: str | None = None,
) -> str:
    environment = os.environ if environ is None else environ
    values = [requested, environment.get("PAPERDELTA_LANG"), (preferences or {}).get("language")]
    for value in values:
        if value and value != "auto":
            if not isinstance(value, str) or not (language := normalize_language(value)):
                raise UnsupportedLanguage(value)
            return language
    system = system_locale
    if system is None:
        system = next(
            (
                environment[name]
                for name in ("LC_ALL", "LC_MESSAGES", "LANG")
                if environment.get(name)
            ),
            None,
        )
    if not system:
        try:
            system = locale.getlocale()[0]
        except (ValueError, TypeError):
            system = None
    return normalize_language(system or "") or "en"


def current_language() -> str:
    return _language.get()


@contextmanager
def language_context(language: str):
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")
    token = _language.set(language)
    try:
        yield
    finally:
        _language.reset(token)


def _parameter(value: Any, language: str) -> Any:
    if isinstance(value, Message):
        return value.render(language)
    if isinstance(value, Exception) and isinstance(getattr(value, "message", None), Message):
        return value.message.render(language)
    if isinstance(value, list) and value and all(isinstance(item, Message) for item in value):
        return "\n".join(item.render(language) for item in value)
    return value


def _render(key: str, parameters: dict, language: str) -> str:
    english = catalog("en")
    if key not in english:
        raise KeyError(f"Unregistered PaperDelta message: {key}")
    template = catalog(language).get(key, english[key])
    return template.format_map(
        {name: _parameter(value, language) for name, value in parameters.items()}
    )


class Message(str):
    """Canonical English text carrying a renderable key through live core results."""

    def __new__(cls, key: str, parameters: dict | None = None, canonical: str | None = None):
        parameters = dict(parameters or {})
        value = canonical if canonical is not None else _render(key, parameters, "en")
        instance = super().__new__(cls, value)
        instance.key = key
        instance.parameters = parameters
        instance.canonical = canonical
        return instance

    def __str__(self):
        return self

    def __getnewargs_ex__(self):
        return (self.key, self.parameters, self.canonical), {}

    def render(self, language: str | None = None) -> str:
        selected = language or current_language()
        if selected == "en" and self.canonical is not None:
            return self.canonical
        return _render(self.key, self.parameters, selected)


def msg(key: str, /, **parameters) -> Message:
    return Message(key, parameters)


class UnsupportedLanguage(ValueError):
    def __init__(self, value):
        self.value = value
        super().__init__(msg("error.LANGUAGE", language=value))


def tr(key: str, /, **parameters) -> str:
    return msg(key, **parameters).render()


def translated(value, language: str | None = None):
    """Translate presentation strings without modifying user text or data types."""
    if isinstance(value, Message):
        return value.render(language)
    if isinstance(value, dict):
        return {key: translated(child, language) for key, child in value.items()}
    if isinstance(value, list):
        return [translated(child, language) for child in value]
    if isinstance(value, tuple):
        return tuple(translated(child, language) for child in value)
    return value


def validate_catalogs() -> list[str]:
    """Return missing keys and placeholder disagreements for build-time validation."""
    english, chinese = catalog("en"), catalog("zh-CN")
    issues = [
        f"Missing {language}: {key}"
        for language, values, other in (("en", english, chinese), ("zh-CN", chinese, english))
        for key in other.keys() - values.keys()
    ]
    formatter = Formatter()
    for key in english.keys() & chinese.keys():
        fields = []
        for text in (english[key], chinese[key]):
            fields.append(
                {
                    (name, spec, conversion)
                    for _, name, spec, conversion in formatter.parse(text)
                    if name is not None
                }
            )
        if fields[0] != fields[1]:
            issues.append(f"Different placeholders: {key}")
    return sorted(issues)
