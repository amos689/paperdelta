"""Shared strict import selection and experiment identity contracts."""

import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from paperdelta.errors import validation_error
from paperdelta.i18n import msg
from paperdelta.models import Source, StrictModel


class IdentityField(StrictModel):
    scope: Literal["param", "tag", "config", "history"]
    field: str = Field(min_length=1, max_length=1000)
    type: Literal["string", "integer"] = "string"


class ImportRequest(StrictModel):
    provider: Literal["file", "mlflow", "wandb"]
    origin: str = Field(min_length=1, max_length=2000)
    source: Source | None = None
    runs: list[str] = Field(default_factory=list, max_length=100)
    metrics: list[str] = Field(default_factory=list, max_length=100)
    identity: dict[Literal["seed", "split", "checkpoint"], IdentityField] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def explicit_selection(self):
        if self.provider == "file":
            if (
                self.source is None
                or self.source.format not in {"csv", "tsv", "xlsx"}
                or self.source.path != self.origin
                or self.runs
                or self.metrics
                or self.identity
            ):
                raise validation_error(msg("export.selection"))
        else:
            if (
                self.source is not None
                or not self.runs
                or not self.metrics
                or len(set(self.runs)) != len(self.runs)
                or len(set(self.metrics)) != len(self.metrics)
                or any(not item or len(item) > 1000 for item in self.metrics)
            ):
                raise validation_error(msg("export.selection"))
            endpoint = urlsplit(self.origin)
            if (
                endpoint.scheme not in {"https", "http"}
                or not endpoint.hostname
                or endpoint.username
                or endpoint.password
                or endpoint.query
                or endpoint.fragment
                or (
                    endpoint.scheme == "http"
                    and endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}
                )
            ):
                raise validation_error(msg("export.endpoint"))
            if self.provider == "mlflow":
                valid = all(re.fullmatch(r"[A-Za-z0-9_-]{1,256}", run) for run in self.runs)
                scopes = {"param", "tag"}
            else:
                valid = all(re.fullmatch(r"[\w.-]+/[\w.-]+/[\w-]+", run) for run in self.runs)
                scopes = {"config", "history"}
            if not valid or any(field.scope not in scopes for field in self.identity.values()):
                raise validation_error(msg("export.selection"))
        return self
