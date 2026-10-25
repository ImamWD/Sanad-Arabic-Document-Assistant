"""queries: queries, citations and llm_perf_samples

Revision ID: 0003_queries
Revises: 0002_documents

`queries` is every question asked, with its outcome (also the future Admin usage log). Enum
values are written out here, not imported from the models, so this revision never changes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_queries"
down_revision: str | None = "0002_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS = {
    "answer_outcome": ("answered", "low_confidence", "no_answer", "error"),
    "answer_band": ("refuse", "low_confidence", "answer"),
    "refusal_reason": ("gate", "sentinel", "no_valid_citation"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS.get(name, ()), name=name, create_type=False)


def upgrade() -> None:
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(op.get_bind())

    op.create_table(
        "queries",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        # sha256 of the session cookie, as in sessions.id. The guest is one shared account, so
        # its history is scoped to the current session. No foreign key: sessions are swept when
        # they expire, and a question asked during a logout must still be stored.
        sa.Column("session_id", sa.Text()),
        sa.Column("question", sa.Text(), nullable=False),
        # Set only when the outcome is answered or low_confidence: discarded text is never kept.
        sa.Column("answer", sa.Text()),
        sa.Column("language", postgresql.ENUM(name="ui_lang", create_type=False), nullable=False),
        sa.Column("outcome", _enum("answer_outcome"), nullable=False),
        sa.Column("band", _enum("answer_band")),
        sa.Column("refusal_reason", _enum("refusal_reason")),
        sa.Column("error_code", sa.Text()),
        sa.Column("top_score", sa.REAL()),
        sa.Column(
            "filters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        # "You may want to check" on a refusal, so the history shows the same titles.
        sa.Column(
            "nearest_document_ids",
            postgresql.ARRAY(sa.Uuid()),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column("llm_provider", sa.Text()),
        sa.Column("llm_model", sa.Text()),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "(refusal_reason IS NOT NULL) = (outcome = 'no_answer')", name="refusal_iff_no_answer"
        ),
        sa.CheckConstraint(
            "(answer IS NOT NULL) = (outcome IN ('answered', 'low_confidence'))",
            name="answer_iff_answered",
        ),
        sa.CheckConstraint(
            "(error_code IS NOT NULL) = (outcome = 'error')", name="error_iff_error"
        ),
    )
    op.create_index("ix_queries_user_created", "queries", ["user_id", sa.text("created_at DESC")])
    op.create_index("ix_queries_session", "queries", ["session_id"])

    op.create_table(
        "citations",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column(
            "query_id", sa.Uuid(), sa.ForeignKey("queries.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("chunks.id"), nullable=False),
        # The [n] marker in the stored answer.
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("score", sa.REAL()),
        sa.UniqueConstraint("query_id", "rank"),
        sa.CheckConstraint("rank >= 1", name="rank_positive"),
    )
    op.create_index("ix_citations_chunk", "citations", ["chunk_id"])

    # Measured generation speed on this machine: the source of the answer-time estimate.
    op.create_table(
        "llm_perf_samples",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("llm_provider", sa.Text(), nullable=False),
        sa.Column("llm_model", sa.Text(), nullable=False),
        sa.Column("prompt_chars", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("prompt_ms", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("output_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_llm_perf_samples_model_created",
        "llm_perf_samples",
        ["llm_model", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("llm_perf_samples")
    op.drop_table("citations")
    op.drop_table("queries")
    for name in ENUMS:
        postgresql.ENUM(name=name).drop(op.get_bind())
