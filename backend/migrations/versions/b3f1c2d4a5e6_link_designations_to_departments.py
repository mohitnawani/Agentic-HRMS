"""Link every designation to exactly one department.

Revision ID: b3f1c2d4a5e6
Revises: 9a31d5e8c204
"""

from alembic import op
import sqlalchemy as sa

revision = "b3f1c2d4a5e6"
down_revision = "9a31d5e8c204"
branch_labels = None
depends_on = None

CANONICAL_DEPARTMENTS = (
    "Human Resources",
    "Engineering / IT",
    "Finance",
    "Sales",
    "Marketing",
    "Operations",
    "Customer Support",
    "Administration",
)

# Known pre-existing titles mapped to their canonical department.
TITLE_TO_DEPARTMENT = {
    "manager": "Administration",
    "hr executive": "Human Resources",
    "hr manager": "Human Resources",
    "recruiter": "Human Resources",
    "talent acquisition specialist": "Human Resources",
    "software engineer": "Engineering / IT",
    "engineering manager": "Engineering / IT",
    "tech lead": "Engineering / IT",
    "backend developer": "Engineering / IT",
    "frontend developer": "Engineering / IT",
    "full-stack developer": "Engineering / IT",
    "qa engineer": "Engineering / IT",
    "devops engineer": "Engineering / IT",
    "finance manager": "Finance",
    "accountant": "Finance",
    "payroll executive": "Finance",
    "financial analyst": "Finance",
    "sales manager": "Sales",
    "sales executive": "Sales",
    "business development executive": "Sales",
    "account manager": "Sales",
    "marketing manager": "Marketing",
    "digital marketing executive": "Marketing",
    "content executive": "Marketing",
    "seo specialist": "Marketing",
    "operations manager": "Operations",
    "operations executive": "Operations",
    "project coordinator": "Operations",
    "support manager": "Customer Support",
    "customer support executive": "Customer Support",
    "technical support executive": "Customer Support",
    "admin manager": "Administration",
    "office administrator": "Administration",
    "administrative executive": "Administration",
}


def _ensure_departments() -> None:
    for name in CANONICAL_DEPARTMENTS:
        op.execute(
            sa.text(
                """
                INSERT INTO departments (id, name, created_at, updated_at)
                SELECT gen_random_uuid(), :name, now(), now()
                WHERE NOT EXISTS (
                    SELECT 1 FROM departments WHERE lower(name) = lower(:name)
                )
                """
            ).bindparams(name=name)
        )


def upgrade() -> None:
    op.add_column(
        "designations", sa.Column("department_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_designations_department_id",
        "designations",
        "departments",
        ["department_id"],
        ["id"],
    )
    _ensure_departments()

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, title FROM designations WHERE department_id IS NULL")
    ).all()
    for row_id, title in rows:
        key = (title or "").strip().lower()
        target = TITLE_TO_DEPARTMENT.get(key, "Administration")
        bind.execute(
            sa.text(
                """
                UPDATE designations SET department_id = (
                    SELECT id FROM departments
                    WHERE lower(name) = lower(:target)
                       OR (lower(:target) = 'engineering / it'
                           AND lower(name) = 'engineering')
                    LIMIT 1
                )
                WHERE id = :row_id
                """
            ).bindparams(target=target, row_id=row_id)
        )
    remaining = bind.execute(
        sa.text("SELECT count(*) FROM designations WHERE department_id IS NULL")
    ).scalar()
    if remaining:
        raise RuntimeError(
            f"{remaining} designation(s) could not be linked to a department"
        )
    op.alter_column(
        "designations", "department_id", existing_type=sa.UUID(), nullable=False
    )


def downgrade() -> None:
    op.drop_constraint("fk_designations_department_id", "designations", type_="foreignkey")
    op.drop_column("designations", "department_id")
