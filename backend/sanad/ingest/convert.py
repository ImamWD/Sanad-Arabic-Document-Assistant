"""DOCX and TXT to PDF with LibreOffice headless (SYSTEM_DESIGN §5.2 step 2).

The PDF rendition *defines* the page numbers we cite for these files, so it must be made
exactly the way the C1b checker (scripts/check_eval.py) makes it: the same soffice flags,
the same TXT import filter, the same TXT decoding order. Both run in the backend image, so
they also share the LibreOffice build and fonts.

TXT is decoded here, not by LibreOffice, which can't detect Windows-1256 (common in Arabic
Windows exports) and would produce mojibake. LibreOffice gets UTF-8 with LF line ends, and
honours form feeds as page breaks.
"""

# ruff: noqa: S603  -- soffice is called with a fixed argument list, never through a shell.
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sanad.core.errors import ErrorCode
from sanad.ingest.errors import IngestionError
from sanad.ingest.filetypes import FileType, looks_like_text

logger = logging.getLogger(__name__)

SOFFICE = "soffice"
TXT_INFILTER = "--infilter=Text (encoded):UTF8,LF,,,"
TXT_ENCODINGS = ("utf-8", "utf-8-sig", "cp1256")
_BOM = "\N{ZERO WIDTH NO-BREAK SPACE}"


def decode_txt(data: bytes) -> str:
    """Decode a TXT upload: UTF-8, then UTF-8 with BOM, then Windows-1256.

    Windows-1256 maps every byte, so anything that isn't text (NUL bytes, UTF-16, binary
    junk) is rejected up front rather than decoded into nonsense.
    """
    if not looks_like_text(data[:65536]):
        raise IngestionError(ErrorCode.TXT_ENCODING_UNKNOWN)
    for encoding in TXT_ENCODINGS:
        try:
            return data.decode(encoding).removeprefix(_BOM)
        except UnicodeDecodeError:
            continue
    raise IngestionError(ErrorCode.TXT_ENCODING_UNKNOWN)  # pragma: no cover - cp1256 maps all


def _profile_dir() -> Path:
    # One LibreOffice profile per worker process: conversions in a process run one at a
    # time, and two soffice processes sharing a profile block each other.
    return Path(tempfile.gettempdir()) / f"sanad-lo-{os.getpid()}"


def to_pdf(src: Path, file_type: FileType, dest: Path, timeout: float) -> None:
    """Write the PDF rendition of a DOCX or TXT file to `dest`."""
    if file_type is FileType.PDF:
        raise ValueError("PDF files are their own rendition")
    if shutil.which(SOFFICE) is None:
        raise RuntimeError("LibreOffice (soffice) is not installed in this image")
    with tempfile.TemporaryDirectory(prefix="sanad-convert-") as tmp:
        work = Path(tmp)
        if file_type is FileType.TXT:
            source = work / "document.txt"
            text = decode_txt(src.read_bytes()).replace("\r\n", "\n")
            source.write_text(text, encoding="utf-8")
            infilter = [TXT_INFILTER]
        else:
            source = work / "document.docx"
            shutil.copyfile(src, source)
            infilter = []
        cmd = [
            SOFFICE,
            "--headless",
            "--norestore",
            f"-env:UserInstallation={_profile_dir().as_uri()}",
            *infilter,
            "--convert-to",
            "pdf",
            "--outdir",
            str(work / "out"),
            str(source),
        ]
        env = {**os.environ, "HOME": tmp}
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, check=False)
        except subprocess.TimeoutExpired:
            logger.warning("LibreOffice timed out after %ss", timeout)
            raise IngestionError(ErrorCode.CONVERSION_FAILED) from None
        output = work / "out" / "document.pdf"
        if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            # soffice's own messages go to the log; they hold paths, never document text.
            logger.warning(
                "LibreOffice conversion failed (exit %s): %s",
                result.returncode,
                result.stderr.decode("utf-8", "replace")[-500:],
            )
            raise IngestionError(ErrorCode.CONVERSION_FAILED)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(output, dest)
