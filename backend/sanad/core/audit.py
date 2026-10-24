"""Append-only audit trail (`audit_events`). Never put document or chunk text in `meta`."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sanad.core.models import AuditEvent


def record(
    db: AsyncSession,
    action: str,
    *,
    actor_id: uuid.UUID | None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    **meta: Any,
) -> None:
    """Add an event to the session; it is written when the caller commits."""
    db.add(
        AuditEvent(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=meta,
        )
    )
