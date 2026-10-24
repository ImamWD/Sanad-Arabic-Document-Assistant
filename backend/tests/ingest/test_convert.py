"""DOCX/TXT -> PDF with LibreOffice, the way the C1b checker does it (conversion parity)."""

import io
import subprocess
import zipfile
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from sanad.core.errors import ErrorCode
from sanad.ingest import convert
from sanad.ingest.convert import decode_txt, to_pdf
from sanad.ingest.errors import IngestionError
from sanad.ingest.filetypes import FileType
from tests.ingest.conftest import SEED, SEED_ENTRIES, needs_seed_files

CONVERTED = [e for e in SEED_ENTRIES if e["format"] in {"docx", "txt"}]


def test_decoding_order_utf8_then_bom_then_windows_1256() -> None:
    text = "محضر اجتماع مجلس الإدارة رقم 4/2017"
    assert decode_txt(text.encode("utf-8")) == text
    assert decode_txt(b"\xef\xbb\xbf" + text.encode("utf-8")) == text
    assert decode_txt(text.encode("cp1256")) == text


def test_text_that_is_not_text_is_refused() -> None:
    for data in (b"\x00\x01binary", "تقرير".encode("utf-16-le")):
        with pytest.raises(IngestionError) as info:
            decode_txt(data)
        assert info.value.code is ErrorCode.TXT_ENCODING_UNKNOWN


def test_checker_and_worker_use_the_same_settings() -> None:
    checker = Path(__file__).resolve().parents[3] / "scripts" / "check_eval.py"
    if not checker.is_file():
        pytest.skip("scripts/check_eval.py arrives with C1b")
    source = checker.read_text(encoding="utf-8")
    assert f'TXT_INFILTER = "{convert.TXT_INFILTER}"' in source
    assert f"TXT_ENCODINGS = {convert.TXT_ENCODINGS!r}" in source
    assert '"--headless"' in source and '"--norestore"' in source


def page_count(pdf: Path) -> int:
    document = pdfium.PdfDocument(str(pdf))
    try:
        return len(document)
    finally:
        document.close()


@needs_seed_files
@pytest.mark.parametrize("entry", CONVERTED, ids=lambda e: e["file"])
def test_seed_docx_and_txt_keep_their_page_count(entry: dict[str, object], tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    to_pdf(
        SEED / "documents" / str(entry["file"]), FileType(str(entry["format"])), out, timeout=180
    )
    assert page_count(out) == entry["page_count"]


def test_a_docx_libreoffice_cannot_read_fails_cleanly(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "not xml at all")
        archive.writestr("word/document.xml", "\x00\x01 not a document")
    bad = tmp_path / "bad.docx"
    bad.write_bytes(buffer.getvalue())
    with pytest.raises(IngestionError) as info:
        to_pdf(bad, FileType.DOCX, tmp_path / "out.pdf", timeout=180)
    assert info.value.code is ErrorCode.CONVERSION_FAILED
    assert not (tmp_path / "out.pdf").exists()


def test_a_conversion_that_hangs_times_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def hang(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="soffice", timeout=1)

    monkeypatch.setattr(subprocess, "run", hang)
    source = tmp_path / "a.txt"
    source.write_text("نص قصير", encoding="utf-8")
    with pytest.raises(IngestionError) as info:
        to_pdf(source, FileType.TXT, tmp_path / "out.pdf", timeout=1)
    assert info.value.code is ErrorCode.CONVERSION_FAILED


def test_pdf_is_never_converted(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="own rendition"):
        to_pdf(tmp_path / "a.pdf", FileType.PDF, tmp_path / "b.pdf", timeout=1)
