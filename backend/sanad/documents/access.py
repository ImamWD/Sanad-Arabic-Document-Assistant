"""Who may see which documents: the one rule for the Library, the viewer and retrieval.

    from sanad.documents.access import retrievable_chunks, visible_documents

    select(Document).where(visible_documents(user))                       # Library, viewer
    select(Chunk).join(Document, Document.id == Chunk.document_id).where(
        retrievable_chunks(user)                                          # retrieval (R1)
    )

- Viewers and the guest never see `restricted` documents (client Q2). Not in the Library, not
  in the viewer (404), and **not in retrieval**: an answer can never draw on one, cited or not.
- The guest sees the synthetic seed documents only (client Q4).
- Archived documents leave the Library and retrieval, but stay reachable by id, so every
  historical citation still opens.

Anything that isn't plainly an editor or admin is treated as a viewer.
"""

from sqlalchemy import ColumnElement, and_, true

from sanad.core.models import Role, User
from sanad.documents.models import ACTIVE_INDEX_GENERATION, Chunk, DocStatus, Document

_SEES_RESTRICTED = frozenset({Role.EDITOR, Role.ADMIN})


def can_see_restricted(user: User) -> bool:
    return not user.is_guest and user.role in _SEES_RESTRICTED


def visible_documents(user: User, *, include_archived: bool = False) -> ColumnElement[bool]:
    """Filter on `Document` for the documents `user` may see."""
    clauses: list[ColumnElement[bool]] = []
    if user.is_guest:
        clauses.append(Document.is_seed.is_(True))
    if not can_see_restricted(user):
        clauses.append(Document.restricted.is_(False))
    if not include_archived:
        clauses.append(Document.is_archived.is_(False))
    return and_(true(), *clauses)


def retrievable_documents(user: User) -> ColumnElement[bool]:
    """Filter on `Document`: what retrieval may read for `user` (visible, not archived,
    fully indexed)."""
    return and_(visible_documents(user), Document.status == DocStatus.READY)


def retrievable_chunks(user: User) -> ColumnElement[bool]:
    """Filter on `Chunk` joined to `Document`: retrievable documents, active index only."""
    return and_(retrievable_documents(user), Chunk.index_generation == ACTIVE_INDEX_GENERATION)
