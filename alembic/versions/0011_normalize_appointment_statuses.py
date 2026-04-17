"""normalize legacy appointment statuses

Revision ID: 0011_appt_status_norm
Revises: 0010_professionals_canon
Create Date: 2026-04-17
"""

from alembic import op


revision = "0011_appt_status_norm"
down_revision = "0010_professionals_canon"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE appointments SET status = 'pending_payment' WHERE status = 'pending'")
    op.execute("UPDATE appointments SET status = 'completed' WHERE status = 'attended'")


def downgrade() -> None:
    # Intentionally left as a no-op to avoid converting valid modern statuses
    # back to legacy values.
    pass
