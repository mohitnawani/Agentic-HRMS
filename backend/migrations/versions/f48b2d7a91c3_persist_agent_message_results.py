"""Persist structured agent results with conversation messages.

Revision ID: f48b2d7a91c3
Revises: e7a9c1d4b2f0
"""

import sqlalchemy as sa
from alembic import op

revision = "f48b2d7a91c3"
down_revision = "e7a9c1d4b2f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_messages", sa.Column("tool_results", sa.JSON(), nullable=True))
    op.add_column("agent_messages", sa.Column("sources", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_messages", "sources")
    op.drop_column("agent_messages", "tool_results")
