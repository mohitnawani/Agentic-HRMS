"""Add durable audit records for agent tool attempts.

Revision ID: c81f2d4a67b0
Revises: b3f1c2d4a5e6
"""

import sqlalchemy as sa
from alembic import op

revision = "c81f2d4a67b0"
down_revision = "b3f1c2d4a5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_tool_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("agent", sa.String(length=30), nullable=False),
        sa.Column("tool", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("permission", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["agent_conversations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_tool_audits_actor_user_id",
        "agent_tool_audits",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_agent_tool_audits_conversation_id",
        "agent_tool_audits",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_tool_audits_conversation_id", table_name="agent_tool_audits"
    )
    op.drop_index(
        "ix_agent_tool_audits_actor_user_id", table_name="agent_tool_audits"
    )
    op.drop_table("agent_tool_audits")
