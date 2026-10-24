"""A fake Sanad API for the eval runner: login, health, documents and ask, over httpx2's
MockTransport. It checks what the real API checks (CSRF header, session cookie, demo
password) and answers each question from a script."""

import json
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx2

from sanad.core.config import get_settings

Page = tuple[str, int]
SESSION = "sanad_session"


@dataclass
class Scripted:
    """One scripted `/api/ask` reply."""

    outcome: str = "answered"
    answer: str | None = None
    cites: Sequence[Page] = ()
    candidates: Sequence[Page] | None = ()  # None: send no diagnostics at all
    band: str | None = "answer"
    refusal_reason: str | None = None
    timings: dict[str, float] = field(default_factory=lambda: {"total": 1200.0})
    status: int = 200
    error_code: str | None = None
    llm_model: str | None = "fake-model"


def answer(text: str, *cites: Page, candidates: Sequence[Page] | None = None) -> Scripted:
    """An answered reply; by default the cited pages are also the top candidates."""
    return Scripted(
        answer=text, cites=cites, candidates=list(cites) if candidates is None else candidates
    )


def refuse(reason: str = "gate", candidates: Sequence[Page] | None = ()) -> Scripted:
    return Scripted(
        outcome="no_answer",
        band="refuse" if reason == "gate" else "answer",
        refusal_reason=reason,
        candidates=candidates,
    )


def http_error(status: int, code: str) -> Scripted:
    return Scripted(status=status, error_code=code)


def seed_document(file: str, **overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "title": file,
        "original_filename": file,
        "status": "ready",
        "is_seed": True,
        "is_archived": False,
        "restricted": False,
    }
    doc.update(overrides)
    return doc


class FakeSanad:
    def __init__(
        self,
        script: dict[str, Scripted | Callable[[int], Scripted]],
        documents: list[dict[str, Any]],
        *,
        health: dict[str, Any] | None = None,
        ollama_version: str | None = "0.40.10",
    ) -> None:
        self.script = script
        self.documents = documents
        self.health_body = health or {"status": "ok", "db": "ok", "ml": "ok"}
        self.ollama = ollama_version
        self.asked: list[dict[str, Any]] = []
        self.calls: dict[str, int] = {}
        self.role: str | None = None
        self._token = uuid.uuid4().hex
        self.transport = httpx2.MockTransport(self.handle)

    def doc_id(self, file: str) -> str:
        return next(str(d["id"]) for d in self.documents if d["original_filename"] == file)

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        self.calls[path] = self.calls.get(path, 0) + 1
        if request.url.host == "ollama":
            if self.ollama is None:
                raise httpx2.ConnectError("no ollama here", request=request)
            return httpx2.Response(200, json={"version": self.ollama})
        if path == "/api/health":
            return httpx2.Response(200, json=self.health_body)
        if request.method == "POST" and request.headers.get("x-sanad") != "1":
            return _error(403, "CSRF_REJECTED")
        if path == "/api/auth/login":
            return self._login(json.loads(request.content))
        if path == "/api/auth/guest":
            return self._signed_in("viewer", guest=True)
        if request.headers.get("cookie") != f"{SESSION}={self._token}":
            return _error(401, "UNAUTHENTICATED")
        if path == "/api/documents":
            return self._documents(request)
        if path == "/api/ask":
            return self._ask(json.loads(request.content))
        return _error(404, "NOT_FOUND")

    def _login(self, body: dict[str, Any]) -> httpx2.Response:
        settings = get_settings()
        accounts = {
            "editor@sanad.example": ("editor", settings.demo_editor_password),
            "admin@sanad.example": ("admin", settings.demo_admin_password),
            "viewer@sanad.example": ("viewer", settings.demo_viewer_password),
        }
        role, password = accounts.get(body.get("email", ""), (None, None))
        if role is None or password is None or body.get("password") != password.get_secret_value():
            return _error(401, "INVALID_CREDENTIALS")
        return self._signed_in(role)

    def _signed_in(self, role: str, *, guest: bool = False) -> httpx2.Response:
        self.role = role
        return httpx2.Response(
            200,
            json={"id": str(uuid.uuid4()), "role": role, "is_guest": guest},
            headers={"set-cookie": f"{SESSION}={self._token}; Path=/api; HttpOnly"},
        )

    def _documents(self, request: httpx2.Request) -> httpx2.Response:
        page = int(request.url.params.get("page", "1"))
        size = int(request.url.params.get("page_size", "25"))
        archived = request.url.params.get("include_archived") == "true"
        docs = [d for d in self.documents if archived or not d["is_archived"]]
        items = docs[(page - 1) * size : page * size]
        return httpx2.Response(
            200, json={"items": items, "total": len(docs), "page": page, "page_size": size}
        )

    def _ask(self, body: dict[str, Any]) -> httpx2.Response:
        self.asked.append(body)
        entry = self.script[body["question"]]
        reply = (
            entry(sum(1 for b in self.asked if b["question"] == body["question"]))
            if callable(entry)
            else entry
        )
        if reply.status != 200:
            return _error(reply.status, reply.error_code or "INTERNAL_ERROR")
        data: dict[str, Any] = {
            "query_id": str(uuid.uuid4()),
            "outcome": reply.outcome,
            "band": reply.band,
            "refusal_reason": reply.refusal_reason,
            "answer": reply.answer if reply.outcome != "no_answer" else None,
            "citations": [
                {
                    "rank": rank,
                    "document_id": self.doc_id(file),
                    "title": file,
                    "page_number": page,
                    "snippet": "...",
                    "char_start": 0,
                    "char_end": 3,
                    "file_type": file.rsplit(".", 1)[-1],
                    "is_converted": not file.endswith(".pdf"),
                }
                for rank, (file, page) in enumerate(reply.cites, start=1)
            ],
            "nearest_documents": [],
        }
        if body.get("debug") and self.role in ("editor", "admin") and reply.candidates is not None:
            data["diagnostics"] = {
                "candidates": [
                    {
                        "rank": rank,
                        "document_id": self.doc_id(file),
                        "page_number": page,
                        "score": round(0.9 - 0.05 * rank, 3),
                    }
                    for rank, (file, page) in enumerate(reply.candidates, start=1)
                ],
                "timings_ms": reply.timings,
                "llm_model": reply.llm_model,
            }
        return httpx2.Response(200, json=data)


def _error(status: int, code: str) -> httpx2.Response:
    return httpx2.Response(status, json={"error": {"code": code, "params": {}}})
