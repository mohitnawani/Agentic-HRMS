"""Remove employee profiles from management-only admin accounts.

Revision ID: e7a9c1d4b2f0
Revises: c81f2d4a67b0
"""

from alembic import op

revision = "e7a9c1d4b2f0"
down_revision = "c81f2d4a67b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    admin_employees = (
        "SELECT employees.id FROM employees "
        "JOIN users ON users.id = employees.user_id "
        "WHERE users.role = 'ADMIN'"
    )
    op.execute(f"DELETE FROM attendance WHERE employee_id IN ({admin_employees})")
    op.execute(f"DELETE FROM leave_requests WHERE employee_id IN ({admin_employees})")
    op.execute(f"DELETE FROM leave_balances WHERE employee_id IN ({admin_employees})")
    op.execute(
        "DELETE FROM employees WHERE user_id IN "
        "(SELECT id FROM users WHERE role = 'ADMIN')"
    )


def downgrade() -> None:
    # Deleted employee-domain data cannot be reconstructed safely.
    pass
