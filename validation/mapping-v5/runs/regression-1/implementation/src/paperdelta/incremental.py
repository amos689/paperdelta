"""Bounded, process-local reuse of parsed inputs and exact metric results.

Callers must read inputs through Project before looking up their content identity.
Final reports, file availability, include graphs and review decisions are never cached.
"""

from __future__ import annotations

import sys
from collections import Counter, OrderedDict
from collections.abc import Callable
from copy import deepcopy
from decimal import Decimal, getcontext
from importlib.metadata import PackageNotFoundError, version
from threading import RLock
from typing import TypeVar

from pydantic import BaseModel

from paperdelta import __version__
from paperdelta.i18n import current_language
from paperdelta.storage import fingerprint

T = TypeVar("T")
MIB = 1024 * 1024


def engine_identity() -> str:
    dependencies = {}
    for name in ("pydantic", "lxml", "pdfplumber", "pdfminer.six", "openpyxl", "markdown-it-py"):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    return fingerprint(
        {"cache": 1, "paperdelta": __version__, "python": sys.version, "dependencies": dependencies}
    )


def _exact(value):
    # Decimal's spelling can affect a displayed result even when values compare equal.
    if isinstance(value, BaseModel):
        return _exact(value.model_dump())
    if isinstance(value, Decimal):
        return ["decimal", str(value)]
    if isinstance(value, dict):
        return ["object", [[key, _exact(item)] for key, item in sorted(value.items())]]
    if isinstance(value, (list, tuple)):
        return ["array", [_exact(item) for item in value]]
    return [type(value).__name__, value]


def retained_size(value, limit: int) -> int:
    """Conservative retained-size accounting, including Word's native XML trees.

    This bounds cached objects, not the whole interpreter or an in-progress parse.
    Stop measuring as soon as the entry cannot fit. Unknown native objects bypass
    caching instead of being assigned an unrealistically small Python wrapper size.
    """
    pending, seen, roots = [value], set(), []
    total = 0
    while pending and total <= limit:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        total += sys.getsizeof(item)
        if type(item) in (str, bytes, int, float, bool, type(None), Decimal):
            continue
        if isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, (list, tuple, set, frozenset)):
            pending.extend(item)
        elif type(item).__module__.startswith("lxml."):
            from lxml import etree

            if not isinstance(item, etree._Element):
                return limit + 1
            root = item.getroottree().getroot()
            if any(root is previous for previous in roots):
                continue
            roots.append(root)
            # Charge the retained tree, including ancestors/siblings behind a node.
            total += 4 * len(etree.tostring(root)) + 1024 * sum(1 for _ in root.iter())
        elif isinstance(item, BaseModel):
            pending.extend(
                [
                    vars(item),
                    item.__pydantic_fields_set__,
                    item.__pydantic_extra__,
                    item.__pydantic_private__,
                ]
            )
        elif hasattr(item, "__dict__"):
            pending.append(vars(item))
        else:
            return limit + 1
    return total


def _private_copy(value, kind):
    copied = deepcopy(value)
    if kind == "document" and hasattr(value, "native_tables"):
        # Table metadata is deliberately indexed by the identity of its rows.
        # Deepcopy preserves integer keys, so rebind them to the copied rows.
        tables = dict(zip(map(id, value.native_tables), map(id, copied.native_tables), strict=True))
        for name in ("table_scopes", "native_table_metadata"):
            if hasattr(copied, name):
                setattr(
                    copied,
                    name,
                    {
                        tables[key]: item
                        for key, item in getattr(copied, name).items()
                        if key in tables
                    },
                )
    return copied


class CheckCache:
    """LRU cache of private copies; no disk state, open handles or error caching."""

    def __init__(self, *, max_bytes=64 * MIB, max_entries=4096, identity=None):
        if type(max_bytes) is not int or type(max_entries) is not int:
            raise ValueError("Cache limits must be integers")
        if not 0 <= max_bytes <= 512 * MIB or not 0 <= max_entries <= 16384:
            raise ValueError("Cache limits exceed the supported bounds")
        self.max_bytes, self.max_entries = max_bytes, max_entries
        self.identity = engine_identity() if identity is None else identity
        self._entries = OrderedDict()
        self._bytes = 0
        self._counts = Counter()
        self._lock = RLock()

    def clear(self, *, identity=None):
        with self._lock:
            self._entries.clear()
            self._bytes = 0
            if identity is not None:
                self.identity = identity

    def stats(self):
        with self._lock:
            return {
                "entries": len(self._entries),
                "retained_bytes": self._bytes,
                "max_entries": self.max_entries,
                "max_bytes": self.max_bytes,
                "counts": dict(self._counts),
            }

    def reuse(self, project, kind: str, identity, compute: Callable[[], T]) -> T:
        context = getcontext()
        key = fingerprint(
            {
                "engine": self.identity,
                "root": str(project.root),
                "language": current_language(),
                "decimal": [
                    context.prec,
                    context.rounding,
                    context.Emin,
                    context.Emax,
                    context.clamp,
                    sorted((signal.__name__, enabled) for signal, enabled in context.traps.items()),
                ],
                "kind": kind,
                "input": _exact(identity),
            }
        )
        with self._lock:
            if key in self._entries:
                value, _ = self._entries[key]
                self._entries.move_to_end(key)
                self._counts[kind + ".hit"] += 1
                return _private_copy(value, kind)
            self._counts[kind + ".miss"] += 1
            value = compute()  # Exceptions never become reusable results.
            limit = min(self.max_bytes // 4, 16 * MIB)
            overhead = sys.getsizeof(key) + 256
            size = retained_size(value, limit) + overhead
            if self.max_entries == 0 or size > limit:
                self._counts[kind + ".bypass"] += 1
                return value
            private = _private_copy(value, kind)
            size = retained_size(private, limit) + overhead
            if size > limit:
                self._counts[kind + ".bypass"] += 1
                return value
            while self._entries and (
                len(self._entries) >= self.max_entries or self._bytes + size > self.max_bytes
            ):
                _, (_, previous_size) = self._entries.popitem(last=False)
                self._bytes -= previous_size
                self._counts["evictions"] += 1
            self._entries[key] = (private, size)
            self._bytes += size
            return value


def reuse(project, kind, identity, compute):
    cache = getattr(project, "check_cache", None)
    return compute() if cache is None else cache.reuse(project, kind, identity, compute)
