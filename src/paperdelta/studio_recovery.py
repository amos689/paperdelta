"""Local draft recovery; a saved draft is never an accepted configuration."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from paperdelta import __version__, builder
from paperdelta.analysis import check_configuration
from paperdelta.config import load_config
from paperdelta.declarations import observe
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.models import StrictModel, VersionOne
from paperdelta.onboarding import Additions, _merge
from paperdelta.patches import _write_lock
from paperdelta.records import validate_record
from paperdelta.sources import EvidenceStore
from paperdelta.storage import fingerprint, json_text, parse_json, sha256

MAX_RECOVERY_BYTES = 4 * 1024 * 1024


class RecoveryRecord(StrictModel):
    recovery_schema_version: VersionOne
    config_path: str
    saved_at: str
    draft: dict | None
    record_id: str


def _compatible_draft(value):
    draft = validate_record(builder.BindingDraft, value, "DRAFT_SCHEMA")
    if draft.draft_id != fingerprint(draft.model_dump(exclude={"draft_id"})):
        raise PaperDeltaError("DRAFT_IDENTITY", msg("builder.identity"))
    if draft.tool_version == __version__:
        return draft
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", draft.tool_version):
        raise PaperDeltaError("DRAFT_IDENTITY", msg("builder.identity"))
    before = tuple(map(int, draft.tool_version.split(".")))
    current = tuple(map(int, __version__.split(".")))
    # These versions share schema 1 and exactly the same binding contracts.
    # Unknown future schemas/versions must be deliberately added after evaluation.
    if len(before) != 3 or before > current or before[:2] not in {(0, 6), (0, 7), (0, 8), (0, 9)}:
        raise PaperDeltaError("DRAFT_IDENTITY", msg("builder.identity"))
    return draft


def migrate_draft(project, value):
    draft = _compatible_draft(value)
    builder._unchanged(project, draft.input_hashes)
    body = draft.model_dump(exclude={"draft_id"})
    body["tool_version"] = __version__
    migrated = {**body, "draft_id": fingerprint(body)}
    builder.resume_draft(project, migrated)
    return migrated


def rebuild_draft(project, value, selected):
    """Recompute explicitly selected old declarations; this never accepts mappings."""
    old = _compatible_draft(value)
    additions = old.additions.model_dump()
    available = {f"{group}:{name}" for group, items in additions.items() for name in items}
    if not selected or len(set(selected)) != len(selected) or not set(selected) <= available:
        raise PaperDeltaError("STUDIO_RECOVERY_SELECTION", msg("recovery.selection"))
    required, pending = set(), list(selected)
    while pending:
        identity = pending.pop()
        if identity in required:
            continue
        required.add(identity)
        group, name = identity.split(":", 1)
        definition = additions[group].get(name)
        if definition is None:
            continue  # Current accepted definitions are shown in the resulting preview.
        if group == "occurrences":
            pending.append("metrics:" + definition["metric"])
        elif group == "claims":
            predicate = definition["predicate"]
            pending.extend(
                "metrics:" + item for item in [predicate["left"], *predicate["candidates"]]
            )
            if isinstance(predicate["right"], str):
                pending.append("metrics:" + predicate["right"])
        elif group == "metrics":
            if "args" in definition:
                pending.extend("metrics:" + item for item in definition["args"])
            else:
                pending.append("sources:" + definition["source"])
    fresh = builder.start_draft(project, old.config_path)
    config, identity = load_config(project, old.config_path)
    chosen = {group: {} for group in additions}
    for identifier in sorted(required):
        group, name = identifier.split(":", 1)
        if name not in additions[group]:
            continue
        definition = additions[group][name]
        if name in getattr(config, group):
            if getattr(config, group)[name].model_dump() != definition:
                raise PaperDeltaError("STUDIO_RECOVERY_NAME", msg("recovery.name", name=identifier))
            continue
        chosen[group][name] = definition
    if not any(chosen.values()):
        raise PaperDeltaError("STUDIO_RECOVERY_EMPTY", msg("recovery.already_accepted"))
    merged = _merge(config, validate_record(Additions, chosen, "DRAFT_SCHEMA"))
    evidence = EvidenceStore(project, merged)
    for name in chosen["sources"]:
        evidence.load_source(name)
    for name in chosen["metrics"]:
        evidence.resolve(name)
    fresh["additions"] = chosen
    fresh["rationale"] = {
        f"{group}:{name}": old.rationale[f"{group}:{name}"]
        for group in ("occurrences", "claims", "figures")
        for name in chosen[group]
    }
    rebuilt = builder._seal(project, fresh, evidence.hashes)
    if any(chosen[group] for group in ("occurrences", "claims", "figures")):
        proposal = builder.finalize_draft(project, rebuilt)  # Refuse unresolved old positions.
        rebuilt = builder._seal(project, rebuilt, proposal["input_hashes"])
    preview = check_configuration(project, merged, old.config_path, identity)
    builder.resume_draft(project, rebuilt)
    return rebuilt, {
        "selected": selected,
        "dependencies": sorted(required - set(selected)),
        "preview": preview,
        "additions": chosen,
        "changed_paths": [
            path
            for path, old_hash in old.input_hashes.items()
            if observe(project, [path]).get(path) != old_hash
        ],
    }


class DraftRecovery:
    def __init__(self, project, config_path):
        self.project = project
        self.config_path = project.relative(project.path(config_path))
        self.path = ".paperdelta/studio/recovery-" + fingerprint(self.config_path)[7:27] + ".json"
        try:
            self.identity = self._identity()
            self.claimed = self.identity is None
        except PaperDeltaError:
            # Inspection still works with an unreadable recovery file. Status
            # exposes the error; subsequent writes cannot overwrite that file.
            self.identity = None
            self.claimed = False

    def _identity(self):
        if not self.project.path(self.path).exists():
            return None
        return sha256(self.project.read(self.path, MAX_RECOVERY_BYTES))

    def read(self):
        if self._identity() is None:
            return None
        record = validate_record(
            RecoveryRecord,
            parse_json(self.project.text(self.path, MAX_RECOVERY_BYTES)[0]),
            "STUDIO_RECOVERY_SCHEMA",
        )
        if record.config_path != self.config_path or record.record_id != fingerprint(
            record.model_dump(exclude={"record_id"})
        ):
            raise PaperDeltaError("STUDIO_RECOVERY_IDENTITY", msg("recovery.identity"))
        return record

    def status(self):
        try:
            record = self.read()
            if record is None or record.draft is None:
                return {"available": False}
            draft = _compatible_draft(record.draft)
            if draft.config_path != self.config_path or draft.draft_id != fingerprint(
                draft.model_dump(exclude={"draft_id"})
            ):
                raise PaperDeltaError("STUDIO_RECOVERY_IDENTITY", msg("recovery.identity"))
            current = observe(self.project, draft.input_hashes)
            changed = [
                path
                for path, identity in draft.input_hashes.items()
                if current.get(path) != identity
            ]
            return {
                "available": True,
                "saved_at": record.saved_at,
                "record_id": record.record_id,
                "draft_id": draft.draft_id,
                "tool_version": draft.tool_version,
                "changed_paths": changed,
                "counts": {
                    group: len(items) for group, items in draft.additions.model_dump().items()
                },
            }
        except PaperDeltaError as exc:
            return {"available": True, "error": exc.code, "message": exc.message}

    def save(self, draft):
        if draft is not None:
            value, _ = builder.resume_draft(self.project, draft)
            if value.config_path != self.config_path:
                raise PaperDeltaError("STUDIO_RECOVERY_IDENTITY", msg("recovery.identity"))
            if self.project.path(self.path) in {
                self.project.path(path) for path in value.input_hashes
            }:
                raise PaperDeltaError("STUDIO_RECOVERY_INPUT", msg("recovery.input"))
            if not any(value.additions.model_dump().values()):
                draft = None
        body = {
            "recovery_schema_version": 1,
            "config_path": self.config_path,
            "saved_at": datetime.now(UTC).isoformat(),
            "draft": draft,
        }
        raw = json_text({**body, "record_id": fingerprint(body)}).encode("utf-8")
        if len(raw) > MAX_RECOVERY_BYTES:
            raise PaperDeltaError("STUDIO_RECOVERY_LIMIT", msg("recovery.limit"))
        with _write_lock(self.project):
            if self._identity() != self.identity:
                raise PaperDeltaError("STUDIO_RECOVERY_CONFLICT", msg("recovery.conflict"))
            record = self.read()
            if not self.claimed and record is not None and record.draft is not None:
                raise PaperDeltaError("STUDIO_RECOVERY_PENDING", msg("recovery.pending"))
            self.project.write(self.path, raw)
            self.identity = sha256(raw)
            self.claimed = True

    def restore(self):
        with _write_lock(self.project):
            record = self.read()
            if record is None or record.draft is None:
                raise PaperDeltaError("STUDIO_RECOVERY_EMPTY", msg("recovery.empty"))
            value = migrate_draft(self.project, record.draft)
            self.identity = self._identity()
            self.claimed = True
        return value

    def select_record(self, record_id):
        record = self.read()
        if record is None or record.record_id != record_id or record.draft is None:
            raise PaperDeltaError("STUDIO_RECOVERY_CONFLICT", msg("recovery.conflict"))
        return record

    def claim_record(self, record_id):
        with _write_lock(self.project):
            self.select_record(record_id)
            self.identity = self._identity()
            self.claimed = True

    def discard(self, record_id):
        self.claim_record(record_id)
        self.save(None)

    def archive(self):
        record = self.read()
        if record is None or record.draft is None:
            return None
        path = ".paperdelta/studio/archives/" + record.record_id[7:] + ".json"
        raw = json_text(record.model_dump()).encode("utf-8")
        if not self.project.path(path).exists():
            self.project.write(path, raw, exclusive=True)
        elif self.project.read(path, MAX_RECOVERY_BYTES) != raw:
            raise PaperDeltaError("STUDIO_RECOVERY_IDENTITY", msg("recovery.identity"))
        return path

    def export(self):
        record = self.read()
        if record is None or record.draft is None:
            raise PaperDeltaError("STUDIO_RECOVERY_EMPTY", msg("recovery.empty"))
        return json_text(record.draft)
