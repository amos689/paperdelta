"""Errors which can be shown to a researcher without a traceback."""

from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from paperdelta.i18n import Message, catalog, msg, translated


class PaperDeltaError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self):
        return self.message

    def render(self, language: str | None = None) -> str:
        return translated(self.message, language)


def validation_error(message: Message) -> PydanticCustomError:
    return PydanticCustomError(
        message.key,
        "{text}",
        {"text": str(message), "message_parameters": message.parameters},
    )


def error_message(error: Exception) -> str:
    """Preserve canonical library diagnostics and provide a localized explanation."""
    if isinstance(error, PaperDeltaError):
        return error.message
    if isinstance(error, ValidationError):
        issues = []
        for issue in error.errors(include_url=False, include_input=False):
            kind, context = issue["type"], issue.get("ctx", {})
            if kind in catalog("en") and "message_parameters" in context:
                detail = Message(kind, context["message_parameters"])
            elif "pydantic." + kind in catalog("en"):
                detail = Message("pydantic." + kind, context)
            else:
                detail = msg("validation.external", kind=kind, detail=issue["msg"])
            location = ".".join(str(part) for part in issue["loc"]) or "$"
            issues.append(msg("validation.item", location=location, detail=detail))
        return Message("validation.summary", {"issues": issues, "count": len(issues)}, str(error))
    return Message("error.external", {"detail": str(error)}, str(error))
