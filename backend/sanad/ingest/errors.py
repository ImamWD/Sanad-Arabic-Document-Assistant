"""The one exception ingestion raises for a document it can't index (SYSTEM_DESIGN §5.2)."""

from typing import Any

from sanad.core.errors import ErrorCode


class IngestionError(Exception):
    """Stored on the document as `error_code` + `error_params` and translated client-side.

    `params` hold only counts and codes, never document text or file paths.
    """

    def __init__(self, code: ErrorCode, **params: Any) -> None:
        super().__init__(code.value)
        self.code = code
        self.params = params
