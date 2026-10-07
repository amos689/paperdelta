"""Bounded, read-only identities for saved Notebook cells and outputs."""

from __future__ import annotations

import re

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.storage import fingerprint, parse_json, sha256


def notebook_error():
    return PaperDeltaError("NOTEBOOK_INVALID", msg("notebook.invalid"))


def _text(value):
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        value = "".join(value)
    if not isinstance(value, str) or len(value) > 1024 * 1024:
        raise notebook_error()
    return value


def inspect_notebook(project, path):
    path = project.relative(project.path(path))
    if ".git" in {part.casefold() for part in path.split("/")}:
        raise PaperDeltaError("PROVENANCE_PRIVATE", msg("provenance.private"))
    raw = project.read(path)
    try:
        value = parse_json(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, PaperDeltaError) as error:
        raise notebook_error() from error
    if (
        not isinstance(value, dict)
        or type(value.get("nbformat")) is not int
        or value["nbformat"] != 4
        or type(value.get("nbformat_minor")) is not int
        or value["nbformat_minor"] < 0
        or not isinstance(value.get("metadata"), dict)
        or not isinstance(value.get("cells"), list)
        or len(value["cells"]) > 2000
    ):
        raise notebook_error()
    cells, ids = [], set()
    for index, cell in enumerate(value["cells"]):
        if not isinstance(cell, dict) or not isinstance(cell.get("metadata"), dict):
            raise notebook_error()
        identifier = cell.get("id")
        if identifier is None and value["nbformat_minor"] < 5:
            identifier = f"index:{index + 1}"
        elif not isinstance(identifier, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,64}", identifier
        ):
            raise notebook_error()
        if identifier in ids:
            raise notebook_error()
        ids.add(identifier)
        source = _text(cell.get("source"))
        kind = cell.get("cell_type")
        if kind not in {"code", "markdown", "raw"}:
            raise notebook_error()
        outputs = cell.get("outputs", [])
        execution = cell.get("execution_count")
        status = "not_code"
        if kind == "code":
            if (
                not isinstance(outputs, list)
                or len(outputs) > 1000
                or (execution is not None and (type(execution) is not int or execution < 0))
            ):
                raise notebook_error()
            status = "saved_outputs" if execution is not None else "unexecuted"
            for output in outputs:
                if not isinstance(output, dict):
                    raise notebook_error()
                output_type = output.get("output_type")
                if output_type == "stream":
                    _text(output.get("text"))
                    if output.get("name") not in {"stdout", "stderr"}:
                        raise notebook_error()
                elif output_type in {"display_data", "execute_result"}:
                    if not isinstance(output.get("data"), dict) or not isinstance(
                        output.get("metadata"), dict
                    ):
                        raise notebook_error()
                    if output_type == "execute_result" and (
                        type(output.get("execution_count")) is not int
                        or output["execution_count"] < 0
                    ):
                        raise notebook_error()
                elif output_type == "error":
                    status = "saved_error"
                else:
                    status = "unsupported_output"
        cells.append(
            {
                "id": identifier,
                "index": index + 1,
                "cell_type": kind,
                "source": source,
                "source_hash": sha256(source.encode("utf-8")),
                "outputs_hash": fingerprint(outputs),
                "outputs_count": len(outputs),
                "execution_count": execution,
                "status": status,
            }
        )
    return {
        "path": path,
        "hash": sha256(raw),
        "nbformat": 4,
        "nbformat_minor": value["nbformat_minor"],
        "cells": cells,
        "executed": False,
        "execution_proven": False,
        "notice": msg("notebook.saved_only"),
    }
