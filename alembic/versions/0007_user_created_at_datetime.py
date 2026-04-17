"""fix user created_at from String to DateTime

Revision ID: 0007_user_created_at_datetime
Revises: 0006_audit_support
Create Date: 2026-04-16 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_user_created_at_datetime"
down_revision = "0006_audit_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {col["name"]: col for col in inspector.get_columns("users")}
    col = columns.get("created_at")
    if col is None:
        return

    col_type = str(col["type"]).upper()
    if "VARCHAR" in col_type or "CHARACTER" in col_type or "TEXT" in col_type:
        op.alter_column(
            "users",
            "created_at",
            existing_type=sa.String(20),
            type_=sa.DateTime(),
            existing_nullable=False,
            postgresql_using="created_at::timestamp",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {col["name"]: col for col in inspector.get_columns("users")}
    col = columns.get("created_at")
    if col is None:
        return

    col_type = str(col["type"]).upper()
    if "TIMESTAMP" in col_type or "DATETIME" in col_type:
        op.alter_column(
            "users",
            "created_at",
            existing_type=sa.DateTime(),
            type_=sa.String(20),
            existing_nullable=False,
            postgresql_using="to_char(created_at, 'YYYY-MM-DD')",
        )
