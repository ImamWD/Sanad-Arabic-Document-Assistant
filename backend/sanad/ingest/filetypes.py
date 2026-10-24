"""What kind of file is this? Checked by content (magic bytes) as well as by extension.

Used at upload (to reject early, before a row exists) and again by the worker, so seeded or
retried files get the same check. A mismatch between extension and content is
UNSUPPORTED_TYPE: an executable renamed to .pdf never reaches a parser.
"""

import zipfile
from enum import StrEnum
from pathlib import Path, PurePath

from sanad.core.errors import ErrorCode
from sanad.ingest.errors import IngestionError

# How much of the file the content sniff reads.
SNIFF_BYTES = 8192
# The PDF header may follow some leading junk, but must start within the first 1 KiB.
_PDF_HEADER_WINDOW = 1024
_ZIP_MAGIC = b"PK\x03\x04"
# Control characters that never occur in a real text file (NUL, and C0 except \t \n \f \r).
_BINARY_BYTES = frozenset(range(0x09)) | {0x0B} | frozenset(range(0x0E, 0x20))
_MAX_BINARY_SHARE = 0.01


class FileType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


def type_from_name(filename: str) -> FileType:
    suffix = PurePath(filename).suffix.lower().lstrip(".")
    try:
        return FileType(suffix)
    except ValueError:
        raise IngestionError(ErrorCode.UNSUPPORTED_TYPE) from None


def looks_like_text(head: bytes) -> bool:
    if not head:
        return True
    if b"\x00" in head:
        return False
    binary = sum(1 for b in head if b in _BINARY_BYTES)
    return binary / len(head) <= _MAX_BINARY_SHARE


def check_content(path: Path, file_type: FileType) -> None:
    """Raise UNSUPPORTED_TYPE unless the file's content matches its declared type."""
    with path.open("rb") as fh:
        head = fh.read(SNIFF_BYTES)
    if file_type is FileType.PDF:
        ok = b"%PDF-" in head[:_PDF_HEADER_WINDOW]
    elif file_type is FileType.DOCX:
        ok = head.startswith(_ZIP_MAGIC) and _is_docx(path)
    else:
        ok = not head.startswith((b"%PDF-", _ZIP_MAGIC)) and looks_like_text(head)
    if not ok:
        raise IngestionError(ErrorCode.UNSUPPORTED_TYPE)


def _is_docx(path: Path) -> bool:
    """A zip that holds a Word document. A zip that can't be read is FILE_CORRUPT."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, OSError):
        raise IngestionError(ErrorCode.FILE_CORRUPT) from None
    return "word/document.xml" in names and "[Content_Types].xml" in names


def detect(path: Path, filename: str) -> FileType:
    """The file's type, from its name, confirmed by its content."""
    file_type = type_from_name(filename)
    check_content(path, file_type)
    return file_type
