"""service cases pqrs

Revision ID: 0012_service_cases
Revises: 0011_appt_status_norm
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_service_cases"
down_revision = "0011_appt_status_norm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("client_user_id", sa.Integer(), nullable=False),
        sa.Column("case_type", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("admin_response", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["client_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_service_cases_id"), "service_cases", ["id"], unique=False)
    op.create_index(op.f("ix_service_cases_appointment_id"), "service_cases", ["appointment_id"], unique=False)
    op.create_index(op.f("ix_service_cases_client_user_id"), "service_cases", ["client_user_id"], unique=False)
    op.create_index(op.f("ix_service_cases_case_type"), "service_cases", ["case_type"], unique=False)
    op.create_index(op.f("ix_service_cases_status"), "service_cases", ["status"], unique=False)
    op.create_index(op.f("ix_service_cases_created_at"), "service_cases", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_service_cases_created_at"), table_name="service_cases")
    op.drop_index(op.f("ix_service_cases_status"), table_name="service_cases")
    op.drop_index(op.f("ix_service_cases_case_type"), table_name="service_cases")
    op.drop_index(op.f("ix_service_cases_client_user_id"), table_name="service_cases")
    op.drop_index(op.f("ix_service_cases_appointment_id"), table_name="service_cases")
    op.drop_index(op.f("ix_service_cases_id"), table_name="service_cases")
    op.drop_table("service_cases")
