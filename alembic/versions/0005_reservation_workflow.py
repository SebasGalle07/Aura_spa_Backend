"""reservation workflow and payment lifecycle

Revision ID: 0005_reservation_workflow
Revises: 0004_email_verification
Create Date: 2026-03-12 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_reservation_workflow"
down_revision = "0004_email_verification"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _foreign_key_exists(inspector, table_name: str, fk_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(fk["name"] == fk_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    appointment_columns = [
        (
            "client_user_id",
            sa.Column("client_user_id", sa.Integer(), nullable=True),
        ),
        (
            "payment_status",
            sa.Column("payment_status", sa.String(length=32), nullable=False, server_default="pending"),
        ),
        (
            "payment_due_at",
            sa.Column("payment_due_at", sa.DateTime(), nullable=True),
        ),
        (
            "deposit_amount",
            sa.Column("deposit_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        ),
        (
            "balance_amount",
            sa.Column("balance_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        ),
        (
            "paid_amount",
            sa.Column("paid_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        ),
        (
            "paid_at",
            sa.Column("paid_at", sa.DateTime(), nullable=True),
        ),
        (
            "payment_method",
            sa.Column("payment_method", sa.String(length=50), nullable=True),
        ),
        (
            "payment_reference",
            sa.Column("payment_reference", sa.String(length=120), nullable=True),
        ),
        (
            "payment_transaction_id",
            sa.Column("payment_transaction_id", sa.String(length=120), nullable=True),
        ),
        (
            "payment_provider",
            sa.Column("payment_provider", sa.String(length=32), nullable=True),
        ),
        (
            "created_at",
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        ),
        (
            "updated_at",
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        ),
        (
            "cancelled_at",
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        ),
    ]

    for column_name, column in appointment_columns:
        if not _column_exists(inspector, "appointments", column_name):
            op.add_column("appointments", column)

    if _column_exists(inspector, "appointments", "created_at") and _column_exists(inspector, "appointments", "updated_at"):
        op.execute("UPDATE appointments SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        op.execute("UPDATE appointments SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
        op.alter_column("appointments", "created_at", server_default=None)
        op.alter_column("appointments", "updated_at", server_default=None)

    if _column_exists(inspector, "appointments", "client_user_id") and not _foreign_key_exists(
        inspector, "appointments", "fk_appointments_client_user_id_users"
    ):
        op.create_foreign_key(
            "fk_appointments_client_user_id_users",
            "appointments",
            "users",
            ["client_user_id"],
            ["id"],
        )

    if not _index_exists(inspector, "appointments", "ix_appointments_client_user_id"):
        op.create_index("ix_appointments_client_user_id", "appointments", ["client_user_id"], unique=False)
    if not _index_exists(inspector, "appointments", "ix_appointments_payment_due_at"):
        op.create_index("ix_appointments_payment_due_at", "appointments", ["payment_due_at"], unique=False)

    if not _table_exists(inspector, "appointment_status_logs"):
        op.create_table(
            "appointment_status_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False),
            sa.Column("from_status", sa.String(length=32), nullable=True),
            sa.Column("to_status", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("actor_type", sa.String(length=32), nullable=False, server_default="system"),
            sa.Column("actor_id", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_appointment_status_logs_id", "appointment_status_logs", ["id"], unique=False)
        op.create_index(
            "ix_appointment_status_logs_appointment_id",
            "appointment_status_logs",
            ["appointment_id"],
            unique=False,
        )

    if not _table_exists(inspector, "payments"):
        op.create_table(
            "payments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False, server_default="mock"),
            sa.Column("method", sa.String(length=50), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="COP"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("provider_reference", sa.String(length=120), nullable=False),
            sa.Column("provider_tx_id", sa.String(length=120), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_payments_id", "payments", ["id"], unique=False)
        op.create_index("ix_payments_appointment_id", "payments", ["appointment_id"], unique=False)
        op.create_index("ix_payments_provider_reference", "payments", ["provider_reference"], unique=True)
        op.create_index("ix_payments_provider_tx_id", "payments", ["provider_tx_id"], unique=True)

    if not _table_exists(inspector, "appointment_reschedules"):
        op.create_table(
            "appointment_reschedules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False),
            sa.Column("old_date", sa.String(length=10), nullable=False),
            sa.Column("old_time", sa.String(length=5), nullable=False),
            sa.Column("new_date", sa.String(length=10), nullable=False),
            sa.Column("new_time", sa.String(length=5), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("actor_type", sa.String(length=32), nullable=False, server_default="system"),
            sa.Column("actor_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_appointment_reschedules_id", "appointment_reschedules", ["id"], unique=False)
        op.create_index(
            "ix_appointment_reschedules_appointment_id",
            "appointment_reschedules",
            ["appointment_id"],
            unique=False,
        )

    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_appointments_professional_date_time_active")
        op.create_index(
            "uq_appointments_professional_date_time_active",
            "appointments",
            ["professional_id", "date", "time"],
            unique=True,
            postgresql_where=sa.text("status IN ('pending_payment', 'confirmed', 'rescheduled')"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_appointments_professional_date_time_active")
        op.create_index(
            "uq_appointments_professional_date_time_active",
            "appointments",
            ["professional_id", "date", "time"],
            unique=True,
            postgresql_where=sa.text("status <> 'cancelled'"),
        )

    if _table_exists(inspector, "appointment_reschedules"):
        if _index_exists(inspector, "appointment_reschedules", "ix_appointment_reschedules_appointment_id"):
            op.drop_index("ix_appointment_reschedules_appointment_id", table_name="appointment_reschedules")
        if _index_exists(inspector, "appointment_reschedules", "ix_appointment_reschedules_id"):
            op.drop_index("ix_appointment_reschedules_id", table_name="appointment_reschedules")
        op.drop_table("appointment_reschedules")

    if _table_exists(inspector, "payments"):
        if _index_exists(inspector, "payments", "ix_payments_provider_tx_id"):
            op.drop_index("ix_payments_provider_tx_id", table_name="payments")
        if _index_exists(inspector, "payments", "ix_payments_provider_reference"):
            op.drop_index("ix_payments_provider_reference", table_name="payments")
        if _index_exists(inspector, "payments", "ix_payments_appointment_id"):
            op.drop_index("ix_payments_appointment_id", table_name="payments")
        if _index_exists(inspector, "payments", "ix_payments_id"):
            op.drop_index("ix_payments_id", table_name="payments")
        op.drop_table("payments")

    if _table_exists(inspector, "appointment_status_logs"):
        if _index_exists(inspector, "appointment_status_logs", "ix_appointment_status_logs_appointment_id"):
            op.drop_index("ix_appointment_status_logs_appointment_id", table_name="appointment_status_logs")
        if _index_exists(inspector, "appointment_status_logs", "ix_appointment_status_logs_id"):
            op.drop_index("ix_appointment_status_logs_id", table_name="appointment_status_logs")
        op.drop_table("appointment_status_logs")

    if _index_exists(inspector, "appointments", "ix_appointments_payment_due_at"):
        op.drop_index("ix_appointments_payment_due_at", table_name="appointments")
    if _index_exists(inspector, "appointments", "ix_appointments_client_user_id"):
        op.drop_index("ix_appointments_client_user_id", table_name="appointments")

    if _foreign_key_exists(inspector, "appointments", "fk_appointments_client_user_id_users"):
        op.drop_constraint("fk_appointments_client_user_id_users", "appointments", type_="foreignkey")

    for column_name in [
        "cancelled_at",
        "updated_at",
        "created_at",
        "payment_provider",
        "payment_transaction_id",
        "payment_reference",
        "payment_method",
        "paid_at",
        "paid_amount",
        "balance_amount",
        "deposit_amount",
        "payment_due_at",
        "payment_status",
        "client_user_id",
    ]:
        if _column_exists(inspector, "appointments", column_name):
            op.drop_column("appointments", column_name)
