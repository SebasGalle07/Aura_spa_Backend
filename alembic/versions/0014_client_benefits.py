"""client pqrs benefits

Revision ID: 0014_client_benefits
Revises: 0013_merge_heads
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_client_benefits"
down_revision = "0013_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_benefits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_user_id", sa.Integer(), nullable=False),
        sa.Column("source_service_case_id", sa.Integer(), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reserved_appointment_id", sa.Integer(), nullable=True),
        sa.Column("used_appointment_id", sa.Integer(), nullable=True),
        sa.Column("granted_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["client_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reserved_appointment_id"], ["appointments.id"]),
        sa.ForeignKeyConstraint(["source_service_case_id"], ["service_cases.id"]),
        sa.ForeignKeyConstraint(["used_appointment_id"], ["appointments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_service_case_id"),
        sa.UniqueConstraint("reserved_appointment_id"),
        sa.UniqueConstraint("used_appointment_id"),
    )
    op.create_index(op.f("ix_client_benefits_id"), "client_benefits", ["id"], unique=False)
    op.create_index(op.f("ix_client_benefits_client_user_id"), "client_benefits", ["client_user_id"], unique=False)
    op.create_index(op.f("ix_client_benefits_source_service_case_id"), "client_benefits", ["source_service_case_id"], unique=False)
    op.create_index(op.f("ix_client_benefits_expires_at"), "client_benefits", ["expires_at"], unique=False)
    op.create_index(op.f("ix_client_benefits_status"), "client_benefits", ["status"], unique=False)

    op.add_column("appointments", sa.Column("service_price_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("appointments", sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("appointments", sa.Column("final_price_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("appointments", sa.Column("applied_benefit_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_appointments_applied_benefit_id",
        "appointments",
        "client_benefits",
        ["applied_benefit_id"],
        ["id"],
    )

    op.execute(
        """
        UPDATE appointments
        SET service_price_amount = COALESCE(NULLIF(paid_amount + balance_amount, 0), deposit_amount + balance_amount, 0),
            final_price_amount = COALESCE(NULLIF(paid_amount + balance_amount, 0), deposit_amount + balance_amount, 0),
            discount_amount = 0
        """
    )

    op.alter_column("appointments", "service_price_amount", server_default=None)
    op.alter_column("appointments", "discount_amount", server_default=None)
    op.alter_column("appointments", "final_price_amount", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_appointments_applied_benefit_id", "appointments", type_="foreignkey")
    op.drop_column("appointments", "applied_benefit_id")
    op.drop_column("appointments", "final_price_amount")
    op.drop_column("appointments", "discount_amount")
    op.drop_column("appointments", "service_price_amount")

    op.drop_index(op.f("ix_client_benefits_status"), table_name="client_benefits")
    op.drop_index(op.f("ix_client_benefits_expires_at"), table_name="client_benefits")
    op.drop_index(op.f("ix_client_benefits_source_service_case_id"), table_name="client_benefits")
    op.drop_index(op.f("ix_client_benefits_client_user_id"), table_name="client_benefits")
    op.drop_index(op.f("ix_client_benefits_id"), table_name="client_benefits")
    op.drop_table("client_benefits")
