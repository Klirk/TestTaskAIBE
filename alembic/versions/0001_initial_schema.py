from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from src.services.rag_service import DEFAULT_ARTICLES

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("ticket_id", sa.String(length=128), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_events_event_id", "webhook_events", ["event_id"], unique=True)
    op.create_index("ix_webhook_events_ticket_id", "webhook_events", ["ticket_id"], unique=False)

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("customer_email", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("reply_url", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("draft_reply", sa.Text(), nullable=True),
        sa.Column("matched_articles", sa.JSON(), nullable=False),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_ticket_id", "tickets", ["ticket_id"], unique=True)
    op.create_index("ix_tickets_event_id", "tickets", ["event_id"], unique=False)
    op.create_index("ix_tickets_status", "tickets", ["status"], unique=False)

    knowledge_table = op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_articles_slug", "knowledge_articles", ["slug"], unique=True)
    op.bulk_insert(knowledge_table, DEFAULT_ARTICLES)

    op.create_table(
        "mock_replies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mock_replies_ticket_id", "mock_replies", ["ticket_id"], unique=True)
    op.create_index(
        "ix_mock_replies_idempotency_key",
        "mock_replies",
        ["idempotency_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mock_replies_idempotency_key", table_name="mock_replies")
    op.drop_index("ix_mock_replies_ticket_id", table_name="mock_replies")
    op.drop_table("mock_replies")
    op.drop_index("ix_knowledge_articles_slug", table_name="knowledge_articles")
    op.drop_table("knowledge_articles")
    op.drop_index("ix_tickets_status", table_name="tickets")
    op.drop_index("ix_tickets_event_id", table_name="tickets")
    op.drop_index("ix_tickets_ticket_id", table_name="tickets")
    op.drop_table("tickets")
    op.drop_index("ix_webhook_events_ticket_id", table_name="webhook_events")
    op.drop_index("ix_webhook_events_event_id", table_name="webhook_events")
    op.drop_table("webhook_events")
