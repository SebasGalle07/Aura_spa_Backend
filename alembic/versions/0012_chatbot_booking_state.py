"""add booking_state to chatbot_conversations

Revision ID: 0012_chatbot_booking_state
Revises: 0011_appt_status_norm
Create Date: 2026-04-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_chatbot_booking_state"
down_revision = "0011_appt_status_norm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chatbot_conversations",
        sa.Column("booking_state", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chatbot_conversations", "booking_state")
