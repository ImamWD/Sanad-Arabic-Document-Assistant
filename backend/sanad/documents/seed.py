"""Init step: register the seed corpus (seed/manifest.json) for ingestion.

Every manifest document whose rendered file is in seed/documents/ is copied onto the `files`
volume and registered as `queued`, with `is_seed = true` and the manifest's `restricted` and
`archived` flags; the worker takes it from there. Idempotent: a seed document that is
already registered (same file name) is left as it is, whatever its status.
"""

import hashlib
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from sanad.core.config import Settings
from sanad.core.models import DocCategory, Programme, Role, User
from sanad.documents.models import DocStatus, Document
from sanad.documents.storage import original_path, resolve
from sanad.ingest.filetypes import FileType
from sanad.ingest.settings import get_ingest_settings
from sanad.ingest.worker import NOTIFY_CHANNEL
from sanad.text.arabic import normalize_for_search

logger = logging.getLogger(__name__)

# The manifest's category names, where they differ from the client's six categories (Q5).
_CATEGORY = {"evaluation": DocCategory.PROGRAMME_EVALUATION, "survey": DocCategory.FIELD_SURVEY}


def _category(name: str | None) -> DocCategory | None:
    if name is None:
        return None
    return _CATEGORY.get(name) or DocCategory(name)


def _title(entry: dict[str, Any]) -> str:
    """The title in the document's own language (Arabic for Arabic and mixed documents)."""
    key = "title_en" if entry.get("language") == "en" else "title_ar"
    return str(entry.get(key) or entry.get("title_en") or entry["file"])


def register_seed_documents(db: Session, settings: Settings) -> None:
    manifest_path = settings.seed_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files_dir = get_ingest_settings().files_dir
    documents_dir = settings.seed_dir / "documents"

    owner = db.scalar(
        select(User.id)
        .where(User.role == Role.ADMIN, User.is_guest.is_(False))
        .order_by(User.created_at)
        .limit(1)
    )
    if owner is None:
        raise RuntimeError("no admin account to own the seed documents")
    programmes = {code: pid for code, pid in db.execute(select(Programme.code, Programme.id))}
    registered = set(
        db.scalars(select(Document.original_filename).where(Document.is_seed.is_(True)))
    )

    added = missing = 0
    for entry in manifest["documents"]:
        filename = str(entry["file"])
        if filename in registered:
            continue
        source = documents_dir / filename
        if not source.is_file():
            missing += 1
            continue
        data = source.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        if db.scalar(
            select(Document.id).where(Document.sha256 == sha256, Document.is_archived.is_(False))
        ):
            logger.warning("seed document %s duplicates an existing document; skipped", filename)
            continue
        document_id = uuid.uuid4()
        file_type = FileType(entry["format"])
        stored = original_path(document_id, file_type)
        dest = resolve(files_dir, stored)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        title = _title(entry)
        db.add(
            Document(
                id=document_id,
                title=title,
                title_norm=normalize_for_search(title),
                original_filename=filename,
                file_path=stored,
                file_type=file_type,
                category=_category(entry.get("category")),
                year=entry.get("year"),
                programme_id=programmes.get(entry.get("programme") or ""),
                uploaded_by=owner,
                status=DocStatus.QUEUED,
                sha256=sha256,
                size_bytes=len(data),
                restricted=bool(entry.get("restricted", False)),
                is_archived=bool(entry.get("archived", False)),
                is_seed=True,
            )
        )
        added += 1
    if added:
        db.execute(text(f"NOTIFY {NOTIFY_CHANNEL}"))
    if missing:
        logger.warning(
            "%d seed documents have no rendered file in %s (render them with make render-seed)",
            missing,
            Path(documents_dir),
        )
    logger.info("seed documents: %d registered, %d already present", added, len(registered))
