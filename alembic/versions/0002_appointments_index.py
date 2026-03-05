"""add appointment indexes

Revision ID: 0002_appointments_index
Revises: 0001_initial
Create Date: 2026-03-05 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_appointments_index"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_appointments_professional_date_time",
        "appointments",
        ["professional_id", "date", "time"],
        unique=False,
    )
    bind = op.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        op.create_index(
            "uq_appointments_professional_date_time_active",
            "appointments",
            ["professional_id", "date", "time"],
            unique=True,
            postgresql_where=sa.text("status <> 'cancelled'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        op.drop_index("uq_appointments_professional_date_time_active", table_name="appointments")
    op.drop_index("ix_appointments_professional_date_time", table_name="appointments")
