"""Project-local display preferences, deliberately separate from scientific inputs."""

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import LANGUAGES, msg
from paperdelta.storage import Project, json_text, parse_json

PREFERENCES_PATH = ".paperdelta/ui.json"


def read_preferences(project: Project) -> dict:
    if not project.path(PREFERENCES_PATH).exists():
        return {}
    text, _ = project.text(PREFERENCES_PATH, limit=16 * 1024)
    value = parse_json(text)
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "language"}
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["language"] not in (*LANGUAGES, "auto")
    ):
        raise PaperDeltaError("UI_SETTINGS", msg("error.UI_SETTINGS"))
    return value


def save_language(project: Project, language: str) -> dict:
    if language not in (*LANGUAGES, "auto"):
        raise PaperDeltaError("LANGUAGE", msg("error.LANGUAGE", language=language))
    value = {"schema_version": 1, "language": language}
    project.write(PREFERENCES_PATH, json_text(value).encode("utf-8"))
    return {"status": "saved", "path": PREFERENCES_PATH, **value}
