"""Local paths, content identity and deterministic serialization."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path, PureWindowsPath
from typing import Any

from pydantic import BaseModel

from paperdelta.errors import PaperDeltaError, error_message
from paperdelta.i18n import msg


def decimal_value(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise PaperDeltaError("INVALID_NUMBER", msg("error.INVALID_NUMBER", value=value))
    if len(str(value)) > 2048:
        raise PaperDeltaError("NUMBER_LIMIT", msg("error.NUMBER_LIMIT.2"))
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise PaperDeltaError("INVALID_NUMBER", msg("error.INVALID_NUMBER.2", value=value)) from exc
    if not number.is_finite():
        raise PaperDeltaError("NONFINITE_NUMBER", msg("error.NONFINITE_NUMBER"))
    if abs(number.as_tuple().exponent) > 1000 or len(number.as_tuple().digits) > 1024:
        raise PaperDeltaError("NUMBER_LIMIT", msg("error.NUMBER_LIMIT.3"))
    return number


def canonical(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return canonical(value.model_dump())
    if isinstance(value, Decimal):
        if value.is_zero():
            return {"$decimal": "0"}
        sign, digits, exponent = value.as_tuple()
        digits = list(digits)
        while digits[-1] == 0:
            digits.pop()
            exponent += 1
        return {"$decimal": f"{'-' if sign else ''}{''.join(map(str, digits))}e{exponent}"}
    if isinstance(value, dict):
        return {str(key): canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    return value


def fingerprint(value: Any) -> str:
    encoded = json.dumps(
        canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(encoded.encode("utf-8"))


def sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def json_text(value: Any) -> str:
    # Preserve Decimal as a JSON number without ever converting through binary float.
    # Turning it into a quoted string would change typed proposal selectors on reload.
    def encode(item: Any, level: int = 0) -> str:
        indent = "  " * (level + 1)
        closing = "  " * level
        if isinstance(item, Decimal):
            return str(decimal_value(item))
        if isinstance(item, dict):
            if not all(isinstance(key, str) for key in item):
                raise PaperDeltaError("JSON_KEY", msg("error.JSON_KEY"))
            parts = [
                json.dumps(key, ensure_ascii=False) + ": " + encode(child, level + 1)
                for key, child in sorted(item.items())
            ]
            return (
                "{\n" + indent + (",\n" + indent).join(parts) + "\n" + closing + "}"
                if parts
                else "{}"
            )
        if isinstance(item, (list, tuple)):
            parts = [encode(child, level + 1) for child in item]
            return (
                "[\n" + indent + (",\n" + indent).join(parts) + "\n" + closing + "]"
                if parts
                else "[]"
            )
        return json.dumps(item, ensure_ascii=False, allow_nan=False)

    return encode(value) + "\n"


def unique_object(pairs: list[tuple[str, Any]]) -> dict:
    obj: dict = {}
    for key, value in pairs:
        if key in obj:
            raise PaperDeltaError("DUPLICATE_KEY", msg("error.DUPLICATE_KEY.2", key=key))
        obj[key] = value
    return obj


def parse_json(text: str) -> Any:
    def reject_constant(value: str) -> None:
        raise PaperDeltaError("NONFINITE_NUMBER", msg("error.NONFINITE_NUMBER.2", value=value))

    try:
        return json.loads(
            text,
            parse_float=decimal_value,
            parse_int=int,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (ValueError, RecursionError) as exc:
        raise PaperDeltaError("INVALID_JSON", error_message(exc)) from exc


class Project:
    def __init__(self, root: Path | str, *, check_cache=None):
        self.check_cache = check_cache
        self.root = Path(root).resolve()

    def path(self, relative: str) -> Path:
        if (
            not isinstance(relative, str)
            or not relative
            or "\x00" in relative
            or PureWindowsPath(relative).drive
        ):
            raise PaperDeltaError("UNSAFE_PATH", msg("error.UNSAFE_PATH", relative=relative))
        path = Path(relative.replace("\\", "/"))
        if path.is_absolute() or any(":" in part for part in path.parts):
            raise PaperDeltaError("UNSAFE_PATH", msg("error.UNSAFE_PATH.2", relative=relative))
        resolved = (self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise PaperDeltaError("UNSAFE_PATH", msg("error.UNSAFE_PATH.3", relative=relative))
        return resolved

    def relative(self, path: Path) -> str:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise PaperDeltaError("UNSAFE_PATH", msg("error.UNSAFE_PATH.4"))
        return resolved.relative_to(self.root).as_posix()

    def read(self, relative: str, limit: int = 32 * 1024 * 1024) -> bytes:
        path = self.path(relative)
        try:
            with path.open("rb") as stream:
                raw = stream.read(limit + 1)
        except OSError as exc:
            raise PaperDeltaError(
                "FILE_UNAVAILABLE",
                msg("error.FILE_UNAVAILABLE", relative=relative, value2=exc.strerror),
            ) from exc
        if len(raw) > limit:
            raise PaperDeltaError(
                "FILE_LIMIT", msg("error.FILE_LIMIT", relative=relative, limit=limit)
            )
        return raw

    def text(self, relative: str, limit: int = 32 * 1024 * 1024) -> tuple[str, bytes]:
        raw = self.read(relative, limit)
        try:
            return raw.decode("utf-8-sig"), raw
        except UnicodeDecodeError as exc:
            raise PaperDeltaError("ENCODING", msg("error.ENCODING.2", relative=relative)) from exc

    def write(self, relative: str, raw: bytes, *, exclusive: bool = False) -> None:
        path = self.path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if exclusive:
            try:
                with path.open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError as exc:
                raise PaperDeltaError(
                    "ALREADY_EXISTS", msg("error.ALREADY_EXISTS.2", relative=relative)
                ) from exc
            return
        temporary: str | None = None
        try:
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
            with tempfile.NamedTemporaryFile(
                dir=path.parent, prefix=".pd-", delete=False
            ) as stream:
                temporary = stream.name
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if mode is not None:
                os.chmod(temporary, mode)
            os.replace(temporary, path)
        finally:
            if temporary is not None and Path(temporary).exists():
                Path(temporary).unlink()
