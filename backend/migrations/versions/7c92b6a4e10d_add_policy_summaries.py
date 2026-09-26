"""Add prebuilt policy summaries.

Revision ID: 7c92b6a4e10d
Revises: f2c4a8d1907b
"""

import sqlalchemy as sa
from alembic import op

revision = "7c92b6a4e10d"
down_revision = "f2c4a8d1907b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("policy_documents", sa.Column("summary", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE policy_documents AS policy
        SET summary = summaries.summary
        FROM (
            SELECT document_id,
                   LEFT(STRING_AGG(content, ' ' ORDER BY chunk_index), 1200) AS summary
            FROM document_chunks
            GROUP BY document_id
        ) AS summaries
        WHERE policy.id = summaries.document_id
          AND policy.summary IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("policy_documents", "summary")
