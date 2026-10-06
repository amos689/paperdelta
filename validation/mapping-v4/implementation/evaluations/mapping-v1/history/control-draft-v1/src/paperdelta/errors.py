"""Errors which can be shown to a researcher without a traceback."""


class PaperDeltaError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
