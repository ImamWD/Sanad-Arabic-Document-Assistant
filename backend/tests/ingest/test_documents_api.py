"""The documents API: upload checks, the visibility rule, Library filters, viewer and lifecycle."""

import io
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from sanad.core.models import AuditEvent, Programme
from sanad.documents.models import Chunk, DocStatus, Document, DocumentPage
from sanad.ingest.filetypes import FileType
from sanad.ingest.settings import IngestSettings, get_ingest_settings
from tests.api.conftest import as_
from tests.ingest.conftest import BAD, DocumentFactory, needs_seed_files

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"

Sessions = dict[str, str]


def upload(
    client: TestClient,
    token: str | None,
    name: str = "report.pdf",
    data: bytes = PDF,
    **form: Any,
) -> Any:
    return client.post(
        "/api/documents",
        headers=as_(token),
        files={"file": (name, data, "application/octet-stream")},
        data={k: str(v).lower() if isinstance(v, bool) else v for k, v in form.items()},
    )


def error(response: Any) -> str:
    body = response.json()
    assert set(body) == {"error"}, body  # a code and params, never a message or a trace
    return str(body["error"]["code"])


def titles(response: Any) -> set[str]:
    assert response.status_code == 200, response.text
    return {item["title"] for item in response.json()["items"]}


# --- upload ------------------------------------------------------------------------------------


def test_an_editor_uploads_a_pdf(
    client: TestClient,
    sessions: Sessions,
    engine: sqlalchemy.Engine,
    ingest_settings: IngestSettings,
) -> None:
    with Session(engine) as db:
        programme = db.scalars(select(Programme).where(Programme.code == "YEP")).one()
    response = upload(
        client,
        sessions["editor"],
        "تقرير التقييم النهائي.pdf",
        category="programme_evaluation",
        year=2022,
        programme_id=str(programme.id),
        restricted=True,
        tags=["تقييم", " تقييم ", "YEP"],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "تقرير التقييم النهائي"
    assert body["original_filename"] == "تقرير التقييم النهائي.pdf"
    assert (body["file_type"], body["is_converted"]) == ("pdf", False)
    assert (body["category"], body["year"]) == ("programme_evaluation", 2022)
    assert body["programme_id"] == str(programme.id)
    assert body["restricted"] is True and body["is_seed"] is False
    assert body["status"] == "queued" and body["error_code"] is None
    assert body["tags"] == ["تقييم", "YEP"]
    assert body["uploaded_by"]["name"] == "Demo Editor"
    assert body["size_bytes"] == len(PDF)
    with Session(engine) as db:
        document = db.get(Document, uuid.UUID(body["id"]))
        assert document is not None
        # Stored under a generated name, never the uploader's.
        assert document.file_path == f"originals/{document.id}.pdf"
        assert (ingest_settings.files_dir / document.file_path).read_bytes() == PDF
        assert (
            db.scalar(select(AuditEvent.action).where(AuditEvent.target_id == document.id))
            == "document.upload"
        )
    assert not any((ingest_settings.files_dir / "incoming").iterdir())


def test_the_same_file_twice_is_a_duplicate(client: TestClient, sessions: Sessions) -> None:
    first = upload(client, sessions["editor"])
    assert first.status_code == 201
    second = upload(client, sessions["admin"], "copy.pdf")
    assert second.status_code == 409
    assert error(second) == "DUPLICATE_DOCUMENT"
    assert second.json()["error"]["params"] == {"document_id": first.json()["id"]}


def test_an_archived_copy_does_not_block_a_new_upload(
    client: TestClient, sessions: Sessions
) -> None:
    first = upload(client, sessions["editor"]).json()
    archived = client.post(
        f"/api/documents/{first['id']}/archive", headers=as_(sessions["editor"]), json={}
    )
    assert archived.status_code == 200
    assert upload(client, sessions["editor"]).status_code == 201
    # ...but unarchiving it now would make two live copies.
    again = client.post(
        f"/api/documents/{first['id']}/unarchive", headers=as_(sessions["editor"]), json={}
    )
    assert again.status_code == 409
    assert error(again) == "DUPLICATE_DOCUMENT"


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("slides.pptx", b"PK\x03\x04..."),
        ("scan.jpg", b"\xff\xd8\xff\xe0JFIF"),
        ("report.pdf", b"MZ\x90\x00 an executable renamed to .pdf"),
        ("report.docx", PDF),
        ("notes.txt", b"\x00\x01\x02\x03 binary"),
    ],
)
def test_wrong_types_are_refused_before_anything_is_stored(
    client: TestClient,
    sessions: Sessions,
    engine: sqlalchemy.Engine,
    ingest_settings: IngestSettings,
    name: str,
    data: bytes,
) -> None:
    response = upload(client, sessions["editor"], name, data)
    assert response.status_code == 415
    assert error(response) == "UNSUPPORTED_TYPE"
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM documents")) == 0
    incoming = ingest_settings.files_dir / "incoming"
    assert not incoming.exists() or not any(incoming.iterdir())


@needs_seed_files
def test_the_disguised_executable_fixture_is_refused(
    client: TestClient, sessions: Sessions
) -> None:
    response = upload(
        client, sessions["editor"], "not-a-pdf.pdf", (BAD / "not-a-pdf.pdf").read_bytes()
    )
    assert response.status_code == 415
    assert error(response) == "UNSUPPORTED_TYPE"


def test_a_damaged_docx_is_accepted_and_left_to_the_worker(
    client: TestClient, sessions: Sessions
) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
    response = upload(client, sessions["editor"], "محضر.docx", buffer.getvalue()[:150])
    assert response.status_code == 201
    assert response.json()["is_converted"] is True


@pytest.fixture
def small_uploads(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "64")
    get_ingest_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_ingest_settings.cache_clear()


def test_a_file_over_the_limit_is_refused(
    client: TestClient, sessions: Sessions, small_uploads: None, engine: sqlalchemy.Engine
) -> None:
    response = upload(client, sessions["editor"], data=PDF + b" " * 100)
    assert response.status_code == 413
    assert error(response) == "FILE_TOO_LARGE"
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM documents")) == 0


def test_an_unknown_programme_is_a_validation_error(client: TestClient, sessions: Sessions) -> None:
    response = upload(client, sessions["editor"], programme_id=str(uuid.uuid4()))
    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "params": {"fields": ["programme_id"]},
    }


@pytest.mark.parametrize("who", ["viewer", "guest"])
def test_viewers_and_the_guest_cannot_upload(
    client: TestClient, sessions: Sessions, who: str
) -> None:
    response = upload(client, sessions[who])
    assert response.status_code == 403
    assert error(response) == "FORBIDDEN"


def test_an_unexpected_failure_is_a_coded_500(
    client: TestClient, sessions: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("disk on fire: /data/files/secret-path")

    monkeypatch.setattr("sanad.api.documents.check_content", explode)
    response = upload(client, sessions["editor"])
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "INTERNAL_ERROR", "params": {}}}
    assert "secret-path" not in response.text


# --- who sees what -----------------------------------------------------------------------------


@pytest.fixture
def library(make_document: DocumentFactory) -> dict[str, Document]:
    return {
        "seed": make_document(title="التقرير السنوي 2021", is_seed=True),
        "seed_restricted": make_document(title="اتفاقية منحة سرية", is_seed=True, restricted=True),
        "seed_archived": make_document(title="مسودة الموازنة 2024", is_seed=True, is_archived=True),
        "staff": make_document(title="Field survey 2025"),
        "staff_restricted": make_document(title="Donor agreement draft", restricted=True),
    }


@pytest.mark.parametrize(
    ("who", "expected"),
    [
        ("guest", {"التقرير السنوي 2021"}),
        ("viewer", {"التقرير السنوي 2021", "Field survey 2025"}),
        (
            "editor",
            {
                "التقرير السنوي 2021",
                "Field survey 2025",
                "اتفاقية منحة سرية",
                "Donor agreement draft",
            },
        ),
        (
            "admin",
            {
                "التقرير السنوي 2021",
                "Field survey 2025",
                "اتفاقية منحة سرية",
                "Donor agreement draft",
            },
        ),
    ],
)
def test_the_library_applies_the_visibility_rule(
    client: TestClient,
    sessions: Sessions,
    library: dict[str, Document],
    who: str,
    expected: set[str],
) -> None:
    response = client.get("/api/documents", headers=as_(sessions[who]))
    assert titles(response) == expected
    assert response.json()["total"] == len(expected)


def test_archived_documents_appear_only_when_asked_for(
    client: TestClient, sessions: Sessions, library: dict[str, Document]
) -> None:
    response = client.get("/api/documents?include_archived=true", headers=as_(sessions["guest"]))
    assert titles(response) == {"التقرير السنوي 2021", "مسودة الموازنة 2024"}


@pytest.mark.parametrize("who", ["viewer", "guest"])
@pytest.mark.parametrize("suffix", ["", "/file", "/pages/1"])
def test_restricted_documents_are_404_for_viewers_and_the_guest(
    client: TestClient,
    sessions: Sessions,
    library: dict[str, Document],
    who: str,
    suffix: str,
) -> None:
    for key in ("seed_restricted", "staff_restricted"):
        response = client.get(
            f"/api/documents/{library[key].id}{suffix}", headers=as_(sessions[who])
        )
        assert response.status_code == 404
        assert error(response) == "NOT_FOUND"


def test_the_guest_cannot_open_staff_documents(
    client: TestClient, sessions: Sessions, library: dict[str, Document]
) -> None:
    response = client.get(f"/api/documents/{library['staff'].id}", headers=as_(sessions["guest"]))
    assert response.status_code == 404
    seed = client.get(f"/api/documents/{library['seed'].id}", headers=as_(sessions["guest"]))
    assert seed.status_code == 200


def test_editors_open_restricted_and_archived_documents_by_id(
    client: TestClient, sessions: Sessions, library: dict[str, Document]
) -> None:
    for key in ("staff_restricted", "seed_archived"):
        response = client.get(f"/api/documents/{library[key].id}", headers=as_(sessions["editor"]))
        assert response.status_code == 200
    # Old citations to an archived document still open for viewers too.
    archived = client.get(
        f"/api/documents/{library['seed_archived'].id}", headers=as_(sessions["viewer"])
    )
    assert archived.status_code == 200


def test_anonymous_requests_are_refused(client: TestClient, library: dict[str, Document]) -> None:
    for path in ("/api/documents", f"/api/documents/{library['seed'].id}"):
        response = client.get(path)
        assert response.status_code == 401
        assert error(response) == "UNAUTHENTICATED"


# --- filters -----------------------------------------------------------------------------------


def test_title_search_is_arabic_normalised(
    client: TestClient, sessions: Sessions, make_document: DocumentFactory
) -> None:
    make_document(title="تقرير التعليــم الأساسي للفتيات")  # tatweel in the title
    make_document(title="الإحصاءات الصحية")
    make_document(title="100% done_report")
    viewer = as_(sessions["viewer"])
    assert titles(client.get("/api/documents?q=التعليم", headers=viewer)) == {
        "تقرير التعليــم الأساسي للفتيات"
    }
    assert titles(client.get("/api/documents?q=الاحصاءات", headers=viewer)) == {"الإحصاءات الصحية"}
    # LIKE wildcards in the query are literal.
    assert titles(client.get("/api/documents?q=%25", headers=viewer)) == {"100% done_report"}
    assert titles(client.get("/api/documents?q=_", headers=viewer)) == {"100% done_report"}


def test_filters_combine(
    client: TestClient,
    sessions: Sessions,
    make_document: DocumentFactory,
    engine: sqlalchemy.Engine,
) -> None:
    with Session(engine) as db:
        yep = db.scalars(select(Programme.id).where(Programme.code == "YEP")).one()
    make_document(title="A", category="annual_report", year=2020)
    make_document(title="B", category="budget", year=2024, programme_id=yep)
    make_document(title="C", year=2021, file_type=FileType.TXT, content=b"plain text")
    make_document(title="D", category="budget", year=2018, status=DocStatus.FAILED)
    viewer = as_(sessions["viewer"])

    def find(query: str) -> set[str]:
        return titles(client.get(f"/api/documents?{query}", headers=viewer))

    assert find("category=budget") == {"B", "D"}
    assert find("uncategorised=true") == {"C"}
    assert find("category=annual_report&uncategorised=true") == {"A", "C"}
    assert find("year_from=2020&year_to=2021") == {"A", "C"}
    assert find("year=2024") == {"B"}
    assert find(f"programme_id={yep}") == {"B"}
    assert find("file_type=txt") == {"C"}
    assert find("status=failed") == {"D"}
    assert find("status=ready&category=budget") == {"B"}
    page = client.get("/api/documents?sort=title&page=2&page_size=3", headers=viewer).json()
    assert [i["title"] for i in page["items"]] == ["D"]
    assert (page["total"], page["page"], page["page_size"]) == (4, 2, 3)


def test_polling_by_ids(
    client: TestClient, sessions: Sessions, make_document: DocumentFactory
) -> None:
    wanted = [make_document(title="X", status=DocStatus.QUEUED), make_document(title="Y")]
    make_document(title="Z")
    ids = "&".join(f"ids={d.id}" for d in wanted)
    assert titles(client.get(f"/api/documents?{ids}", headers=as_(sessions["editor"]))) == {
        "X",
        "Y",
    }


def test_the_restricted_filter_is_for_editors(
    client: TestClient, sessions: Sessions, library: dict[str, Document]
) -> None:
    editor = client.get("/api/documents?restricted=true", headers=as_(sessions["editor"]))
    assert titles(editor) == {"اتفاقية منحة سرية", "Donor agreement draft"}
    viewer = client.get("/api/documents?restricted=true", headers=as_(sessions["viewer"]))
    assert titles(viewer) == {"التقرير السنوي 2021", "Field survey 2025"}


# --- viewer file and page text -----------------------------------------------------------------


def test_the_viewer_pdf_is_served_inline(
    client: TestClient, sessions: Sessions, make_document: DocumentFactory
) -> None:
    document = make_document(content=PDF, is_seed=True)
    response = client.get(f"/api/documents/{document.id}/file", headers=as_(sessions["guest"]))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.content == PDF


def test_a_document_without_a_rendition_yet_is_not_ready(
    client: TestClient, sessions: Sessions, make_document: DocumentFactory
) -> None:
    document = make_document(
        file_type=FileType.DOCX, content=b"PK\x03\x04", status=DocStatus.QUEUED
    )
    for suffix in ("/file", "/pages/1"):
        response = client.get(
            f"/api/documents/{document.id}{suffix}", headers=as_(sessions["viewer"])
        )
        assert response.status_code == 409
        assert error(response) == "DOCUMENT_NOT_READY"


def test_page_text_comes_with_its_chunk_spans(
    client: TestClient,
    sessions: Sessions,
    make_document: DocumentFactory,
    engine: sqlalchemy.Engine,
) -> None:
    document = make_document(page_count=2)
    page = "عن المؤسسة\n\nتأسست المؤسسة عام 2014."
    with engine.begin() as conn:
        conn.execute(
            insert(DocumentPage),
            [
                {
                    "document_id": document.id,
                    "page_number": 1,
                    "text": page,
                    "text_norm": page,
                    "char_count": len(page),
                },
                {
                    "document_id": document.id,
                    "page_number": 2,
                    "text": "",
                    "text_norm": "",
                    "char_count": 0,
                },
            ],
        )
        conn.execute(
            insert(Chunk).values(
                document_id=document.id,
                page_number=1,
                chunk_index=0,
                text=page,
                text_norm=page,
                char_start=0,
                char_end=len(page),
                token_count=9,
                embedding=[0.0] * 1024,
                embedding_model="test",
            )
        )
    response = client.get(f"/api/documents/{document.id}/pages/1", headers=as_(sessions["viewer"]))
    assert response.status_code == 200
    body = response.json()
    assert (body["page_number"], body["page_count"], body["text"]) == (1, 2, page)
    assert [(c["chunk_index"], c["char_start"], c["char_end"]) for c in body["chunks"]] == [
        (0, 0, len(page))
    ]
    empty = client.get(f"/api/documents/{document.id}/pages/2", headers=as_(sessions["viewer"]))
    assert empty.json()["chunks"] == []
    missing = client.get(f"/api/documents/{document.id}/pages/3", headers=as_(sessions["viewer"]))
    assert missing.status_code == 404
    zero = client.get(f"/api/documents/{document.id}/pages/0", headers=as_(sessions["viewer"]))
    assert zero.status_code == 422


# --- metadata and lifecycle --------------------------------------------------------------------


def test_editors_edit_metadata(
    client: TestClient, sessions: Sessions, make_document: DocumentFactory
) -> None:
    document = make_document(title="old", category="budget", year=2018)
    editor = as_(sessions["editor"])
    response = client.patch(
        f"/api/documents/{document.id}",
        headers=editor,
        json={
            "title": "  الموازنة   2018 ",
            "category": None,
            "tags": ["مالية"],
            "restricted": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["title"], body["category"], body["year"]) == ("الموازنة 2018", None, 2018)
    assert (body["tags"], body["restricted"]) == (["مالية"], True)
    assert titles(client.get("/api/documents?q=الموازنه", headers=editor)) == {"الموازنة 2018"}
    # Restricted now: gone for viewers.
    hidden = client.get(f"/api/documents/{document.id}", headers=as_(sessions["viewer"]))
    assert hidden.status_code == 404


@pytest.mark.parametrize(
    "body",
    [{"title": None}, {"title": ""}, {"restricted": None}, {"year": 1800}, {"category": "other"}],
)
def test_invalid_edits_are_refused(
    client: TestClient, sessions: Sessions, make_document: DocumentFactory, body: dict[str, Any]
) -> None:
    document = make_document()
    response = client.patch(
        f"/api/documents/{document.id}", headers=as_(sessions["editor"]), json=body
    )
    assert response.status_code == 422
    assert error(response) == "VALIDATION_ERROR"


@pytest.mark.parametrize("who", ["viewer", "guest"])
def test_viewers_cannot_change_documents(
    client: TestClient, sessions: Sessions, make_document: DocumentFactory, who: str
) -> None:
    document = make_document(is_seed=True, status=DocStatus.FAILED)
    calls = [
        ("PATCH", "", {"title": "x"}),
        ("POST", "/archive", {}),
        ("POST", "/unarchive", {}),
        ("POST", "/retry", {}),
    ]
    for method, suffix, body in calls:
        response = client.request(
            method, f"/api/documents/{document.id}{suffix}", headers=as_(sessions[who]), json=body
        )
        assert response.status_code == 403, (method, suffix)


def test_archive_and_unarchive(
    client: TestClient, sessions: Sessions, make_document: DocumentFactory
) -> None:
    document = make_document(title="أرشيف")
    editor = as_(sessions["editor"])
    archived = client.post(f"/api/documents/{document.id}/archive", headers=editor, json={}).json()
    assert archived["is_archived"] is True
    assert titles(client.get("/api/documents", headers=editor)) == set()
    restored = client.post(
        f"/api/documents/{document.id}/unarchive", headers=editor, json={}
    ).json()
    assert restored["is_archived"] is False
    assert titles(client.get("/api/documents", headers=editor)) == {"أرشيف"}


def test_retry_requeues_a_failed_document(
    client: TestClient,
    sessions: Sessions,
    make_document: DocumentFactory,
    engine: sqlalchemy.Engine,
) -> None:
    failed = make_document(status=DocStatus.FAILED, attempts=3)
    response = client.post(
        f"/api/documents/{failed.id}/retry", headers=as_(sessions["editor"]), json={}
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["error_code"], body["error_params"]) == ("queued", None, None)
    with Session(engine) as db:
        assert db.scalar(select(Document.attempts).where(Document.id == failed.id)) == 0

    ready = make_document()
    again = client.post(
        f"/api/documents/{ready.id}/retry", headers=as_(sessions["editor"]), json={}
    )
    assert again.status_code == 409
    assert error(again) == "DOCUMENT_NOT_RETRYABLE"


def test_unknown_documents_are_404(client: TestClient, sessions: Sessions, accounts: Any) -> None:
    for method, suffix in [("GET", ""), ("GET", "/file"), ("POST", "/archive"), ("PATCH", "")]:
        response = client.request(
            method,
            f"/api/documents/{uuid.uuid4()}{suffix}",
            headers=as_(sessions["editor"]),
            json={},
        )
        assert response.status_code == 404
        assert error(response) == "NOT_FOUND"


def test_files_dir_path_escapes_are_refused(tmp_path: Path) -> None:
    from sanad.documents.storage import resolve

    assert resolve(tmp_path, "originals/x.pdf") == (tmp_path / "originals" / "x.pdf").resolve()
    with pytest.raises(ValueError, match="escapes"):
        resolve(tmp_path, "../etc/passwd")
