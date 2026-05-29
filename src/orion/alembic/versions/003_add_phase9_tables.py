"""Add approval_records and agent_memory tables.

Revision ID: 003_add_phase9_tables
Revises:
Create Date: 2026-05-29

Phase 9 — Human Approval Steps & Agent Memory Persistence.
"""

from alembic import op
import sqlalchemy as sa

revision = "003_add_phase9_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # approval_records table (Part A)
    op.create_table(
        "approval_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("decided_by", sa.String(), server_default=""),
        sa.Column("reason", sa.String(), server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approval_records_request_id", "approval_records", ["request_id"])
    op.create_index("ix_approval_records_workflow_id", "approval_records", ["workflow_id"])

    # agent_memory table (Part B)
    op.create_table(
        "agent_memory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.String(length=65535), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_memory_agent_id", "agent_memory", ["agent_id"])
    op.create_index("ix_agent_memory_session_id", "agent_memory", ["session_id"])
    op.create_index("ix_agent_memory_created_at", "agent_memory", ["created_at"])
    op.create_index(
        "ix_agent_memory_agent_session_sequence",
        "agent_memory",
        ["agent_id", "session_id", "sequence_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_memory_agent_session_sequence", "agent_memory")
    op.drop_index("ix_agent_memory_created_at", "agent_memory")
    op.drop_index("ix_agent_memory_session_id", "agent_memory")
    op.drop_index("ix_agent_memory_agent_id", "agent_memory")
    op.drop_table("agent_memory")

    op.drop_index("ix_approval_records_workflow_id", "approval_records")
    op.drop_index("ix_approval_records_request_id", "approval_records")
    op.drop_table("approval_records")
