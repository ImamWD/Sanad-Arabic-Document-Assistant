import io
import zipfile
from pathlib import Path

import pytest

from sanad.core.errors import ErrorCode
from sanad.ingest.errors import IngestionError
from sanad.ingest.filetypes import FileType, check_content, detect, looks_like_text, type_from_name
from tests.ingest.conftest import BAD, SEED, needs_seed_files


def write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def docx_bytes(*, document: bool = True) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        if document:
            archive.writestr("word/document.xml", "<w:document/>")
        else:
            archive.writestr("xl/workbook.xml", "<workbook/>")
    return buffer.getvalue()


def code_of(path: Path, file_type: FileType) -> ErrorCode | None:
    try:
        check_content(path, file_type)
    except IngestionError as exc:
        return exc.code
    return None


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("report.pdf", FileType.PDF),
        ("REPORT.PDF", FileType.PDF),
        ("محضر الاجتماع.docx", FileType.DOCX),
        ("notes.txt", FileType.TXT),
        ("archive.tar.txt", FileType.TXT),
    ],
)
def test_type_from_name(name: str, expected: FileType) -> None:
    assert type_from_name(name) is expected


@pytest.mark.parametrize("name", ["slides.pptx", "scan.jpg", "report", "report.doc", ".pdf.exe"])
def test_other_extensions_are_unsupported(name: str) -> None:
    with pytest.raises(IngestionError) as info:
        type_from_name(name)
    assert info.value.code is ErrorCode.UNSUPPORTED_TYPE


def test_content_must_match_the_extension(tmp_path: Path) -> None:
    pdf = write(tmp_path, "a.pdf", b"%PDF-1.7\n...")
    docx = write(tmp_path, "a.docx", docx_bytes())
    text = write(tmp_path, "a.txt", "محضر اجتماع مجلس الإدارة\f2017".encode("cp1256"))
    assert code_of(pdf, FileType.PDF) is None
    assert code_of(docx, FileType.DOCX) is None
    assert code_of(text, FileType.TXT) is None
    assert code_of(pdf, FileType.DOCX) is ErrorCode.UNSUPPORTED_TYPE
    assert code_of(pdf, FileType.TXT) is ErrorCode.UNSUPPORTED_TYPE
    assert code_of(docx, FileType.PDF) is ErrorCode.UNSUPPORTED_TYPE
    assert code_of(docx, FileType.TXT) is ErrorCode.UNSUPPORTED_TYPE
    assert detect(docx, "minutes.docx") is FileType.DOCX


def test_pdf_header_may_follow_a_little_junk(tmp_path: Path) -> None:
    assert code_of(write(tmp_path, "a.pdf", b"\n\r junk %PDF-1.4"), FileType.PDF) is None
    late = write(tmp_path, "b.pdf", b" " * 2000 + b"%PDF-1.4")
    assert code_of(late, FileType.PDF) is ErrorCode.UNSUPPORTED_TYPE


def test_a_zip_that_is_not_a_word_document_is_unsupported(tmp_path: Path) -> None:
    xlsx = write(tmp_path, "a.docx", docx_bytes(document=False))
    assert code_of(xlsx, FileType.DOCX) is ErrorCode.UNSUPPORTED_TYPE


def test_a_broken_zip_is_corrupt(tmp_path: Path) -> None:
    broken = write(tmp_path, "a.docx", docx_bytes()[:200])
    assert code_of(broken, FileType.DOCX) is ErrorCode.FILE_CORRUPT


def test_binary_and_utf16_text_files(tmp_path: Path) -> None:
    binary = write(tmp_path, "a.txt", b"MZ\x90\x00\x03\x00\x00\x00" * 100)
    utf16 = write(tmp_path, "b.txt", "تقرير".encode("utf-16"))
    empty = write(tmp_path, "c.txt", b"")
    assert code_of(binary, FileType.TXT) is ErrorCode.UNSUPPORTED_TYPE
    assert code_of(utf16, FileType.TXT) is ErrorCode.TXT_ENCODING_UNKNOWN
    assert code_of(empty, FileType.TXT) is None


def test_looks_like_text() -> None:
    assert looks_like_text(b"")
    assert looks_like_text("سطر\tأول\r\nسطر ثانٍ\f".encode())
    assert not looks_like_text(b"abc\x00def")
    assert not looks_like_text(b"\x01\x02\x03" + b"a" * 100)


@needs_seed_files
def test_the_executable_disguised_as_a_pdf_is_unsupported() -> None:
    assert code_of(BAD / "not-a-pdf.pdf", FileType.PDF) is ErrorCode.UNSUPPORTED_TYPE


@needs_seed_files
@pytest.mark.parametrize("path", sorted((SEED / "documents").glob("*.*")), ids=lambda p: p.name)
def test_every_seed_document_passes_the_content_check(path: Path) -> None:
    assert detect(path, path.name) is FileType(path.suffix.lstrip("."))
