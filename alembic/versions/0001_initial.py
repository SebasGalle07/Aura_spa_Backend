"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-28 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.String(length=20), nullable=False),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("image", sa.String(), nullable=True),
    )
    op.create_index(op.f("ix_services_id"), "services", ["id"], unique=False)

    op.create_table(
        "professionals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("specialty", sa.String(length=255), nullable=False),
        sa.Column("schedule_start", sa.String(length=10), nullable=False),
        sa.Column("schedule_end", sa.String(length=10), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index(op.f("ix_professionals_id"), "professionals", ["id"], unique=False)

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_name", sa.String(length=255), nullable=False),
        sa.Column("client_email", sa.String(length=255), nullable=False),
        sa.Column("client_phone", sa.String(length=50), nullable=True),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("professional_id", sa.Integer(), sa.ForeignKey("professionals.id"), nullable=False),
        sa.Column("date", sa.String(length=10), nullable=False),
        sa.Column("time", sa.String(length=5), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.String(), nullable=False, server_default=""),
        sa.Column("history", sa.JSON(), nullable=False),
    )
    op.create_index(op.f("ix_appointments_id"), "appointments", ["id"], unique=False)

    op.create_table(
        "company_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_name", sa.String(length=255), nullable=True),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("nit", sa.String(length=50), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("week_start", sa.String(length=10), nullable=True),
        sa.Column("week_end", sa.String(length=10), nullable=True),
        sa.Column("sat_start", sa.String(length=10), nullable=True),
        sa.Column("sat_end", sa.String(length=10), nullable=True),
        sa.Column("sun_start", sa.String(length=10), nullable=True),
        sa.Column("sun_end", sa.String(length=10), nullable=True),
        sa.Column("instagram", sa.String(length=255), nullable=True),
        sa.Column("facebook", sa.String(length=255), nullable=True),
        sa.Column("whatsapp", sa.String(length=50), nullable=True),
        sa.Column("welcome_msg", sa.String(), nullable=True),
        sa.Column("sp_logo", sa.String(), nullable=True),
        sa.Column("landing_section1", sa.String(), nullable=True),
        sa.Column("landing_section2", sa.String(), nullable=True),
        sa.Column("landing_section3", sa.String(), nullable=True),
    )
    op.create_index(op.f("ix_company_data_id"), "company_data", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_company_data_id"), table_name="company_data")
    op.drop_table("company_data")
    op.drop_index(op.f("ix_appointments_id"), table_name="appointments")
    op.drop_table("appointments")
    op.drop_index(op.f("ix_professionals_id"), table_name="professionals")
    op.drop_table("professionals")
    op.drop_index(op.f("ix_services_id"), table_name="services")
    op.drop_table("services")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
