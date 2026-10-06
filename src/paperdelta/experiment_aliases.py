"""Explicit paper labels for declared identities; numeric results are never aliases."""

from pydantic import Field, model_validator

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.models import StrictModel
from paperdelta.sources import typed_cell


class IdentityAlias(StrictModel):
    column: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=1000)
    label: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def meaningful_label(self):
        if not self.label.strip() or not self.rationale.strip():
            raise PaperDeltaError("EXPERIMENT_ALIAS_CONFLICT", msg("experiment.alias_conflict"))
        return self


def validated_aliases(request, source, rows):
    result, labels = [], {}
    identity_columns = set(request.group_by) | set(request.where)
    for alias in request.aliases:
        if alias.column not in identity_columns or alias.column in request.fields:
            raise PaperDeltaError("EXPERIMENT_ALIAS_COLUMN", msg("experiment.alias_column"))
        value = typed_cell(alias.value, source.columns[alias.column], alias.column)
        if not any(row["values"][alias.column] == value for row in rows):
            raise PaperDeltaError("EXPERIMENT_ALIAS_VALUE", msg("experiment.alias_value"))
        key = (alias.column, alias.label.strip().casefold())
        if not key[1] or (key in labels and labels[key] != value):
            raise PaperDeltaError("EXPERIMENT_ALIAS_CONFLICT", msg("experiment.alias_conflict"))
        labels[key] = value
        result.append({**alias.model_dump(), "value": value})
    return result
