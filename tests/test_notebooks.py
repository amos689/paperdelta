from copy import deepcopy

import pytest

from paperdelta.errors import PaperDeltaError
from paperdelta.notebooks import inspect_notebook
from paperdelta.storage import Project, json_text


def notebook():
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {
                "id": "train-result",
                "cell_type": "code",
                "metadata": {},
                "source": ["raise RuntimeError('Do not execute during inspection')\n"],
                "execution_count": 2,
                "outputs": [{"output_type": "stream", "name": "stdout", "text": ["84.1", "%\n"]}],
            }
        ],
    }


def test_saved_cell_identity_and_outputs_are_read_without_execution(tmp_path):
    store = Project(tmp_path)
    value = notebook()
    store.write("analysis.ipynb", json_text(value).encode())
    result = inspect_notebook(store, "analysis.ipynb")
    assert not result["executed"] and not result["execution_proven"]
    assert result["cells"][0]["id"] == "train-result"
    assert result["cells"][0]["status"] == "saved_outputs"
    value["cells"][0]["source"] = "print('changed code, saved output retained')"
    store.write("analysis.ipynb", json_text(value).encode())
    changed = inspect_notebook(store, "analysis.ipynb")
    assert changed["cells"][0]["source_hash"] != result["cells"][0]["source_hash"]
    assert changed["cells"][0]["outputs_hash"] == result["cells"][0]["outputs_hash"]
    assert changed["hash"] != result["hash"]


@pytest.mark.parametrize("change", ["duplicate", "missing_id", "boolean_count", "bad_text"])
def test_notebook_identity_and_saved_state_cannot_be_inferred_from_invalid_fields(tmp_path, change):
    value = notebook()
    if change == "duplicate":
        value["cells"].append(deepcopy(value["cells"][0]))
    elif change == "missing_id":
        del value["cells"][0]["id"]
    elif change == "boolean_count":
        value["cells"][0]["execution_count"] = True
    else:
        value["cells"][0]["source"] = ["print(1)", 2]
    store = Project(tmp_path)
    store.write("analysis.ipynb", json_text(value).encode())
    with pytest.raises(PaperDeltaError) as error:
        inspect_notebook(store, "analysis.ipynb")
    assert error.value.code == "NOTEBOOK_INVALID"


def test_old_notebook_uses_explicit_index_identity_and_unexecuted_state(tmp_path):
    value = notebook()
    value["nbformat_minor"] = 4
    del value["cells"][0]["id"]
    value["cells"][0]["execution_count"] = None
    store = Project(tmp_path)
    store.write("analysis.ipynb", json_text(value).encode())
    cell = inspect_notebook(store, "analysis.ipynb")["cells"][0]
    assert cell["id"] == "index:1" and cell["status"] == "unexecuted"
