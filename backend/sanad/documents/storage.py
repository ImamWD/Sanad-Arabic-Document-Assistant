"""Where document files live on the `files` volume (FILES_DIR).

Paths are generated from the document id and never from the uploader's file name, and the
database stores them relative to FILES_DIR:

    originals/<id>.<pdf|docx|txt>   the file as uploaded
    viewer/<id>.pdf                 the LibreOffice rendition of a DOCX or TXT file
"""

import uuid
from pathlib import Path

from sanad.ingest.filetypes import FileType


def original_path(document_id: uuid.UUID, file_type: FileType) -> str:
    return f"originals/{document_id}.{file_type.value}"


def rendition_path(document_id: uuid.UUID) -> str:
    return f"viewer/{document_id}.pdf"


def resolve(files_dir: Path, relative: str) -> Path:
    """The absolute path of a stored file; refuses anything that escapes FILES_DIR."""
    root = files_dir.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("stored path escapes FILES_DIR")
    return path
