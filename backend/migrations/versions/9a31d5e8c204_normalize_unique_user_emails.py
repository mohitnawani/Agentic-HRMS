"""Normalize user emails and enforce case-insensitive uniqueness.

Revision ID: 9a31d5e8c204
Revises: 7c92b6a4e10d
"""

from alembic import op

revision = "9a31d5e8c204"
down_revision = "7c92b6a4e10d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM users
                GROUP BY lower(trim(email))
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION 'Duplicate user emails exist when compared case-insensitively';
            END IF;
        END $$
        """
    )
    op.execute("UPDATE users SET email = lower(trim(email))")
    op.execute("CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_email_lower")
