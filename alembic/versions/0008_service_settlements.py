"""service settlements and receipts

Revision ID: 0008_service_settlements
Revises: 0007_user_created_at_datetime
Create Date: 2026-04-17 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_service_settlements"
down_revision = "0007_user_created_at_datetime"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _create_index_if_missing(inspector, name: str, table: str, columns: list[str], unique: bool = False) -> None:
    if not _index_exists(inspector, table, name):
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "service_settlements"):
        op.create_table(
            "service_settlements",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("appointment_id", sa.Integer(), sa.ForeignKey("appointments.id"), nullable=False),
            sa.Column("client_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id"), nullable=False),
            sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("deposit_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("balance_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("paid_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_settlement"),
            sa.Column("settled_at", sa.DateTime(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("appointment_id", name="uq_service_settlements_appointment_id"),
        )
        _create_index_if_missing(inspector, "ix_service_settlements_id", "service_settlements", ["id"])
        _create_index_if_missing(
            inspector,
            "ix_service_settlements_appointment_id",
            "service_settlements",
            ["appointment_id"],
            unique=True,
        )
        _create_index_if_missing(
            inspector,
            "ix_service_settlements_client_user_id",
            "service_settlements",
            ["client_user_id"],
        )
        _create_index_if_missing(inspector, "ix_service_settlements_service_id", "service_settlements", ["service_id"])
        _create_index_if_missing(inspector, "ix_service_settlements_status", "service_settlements", ["status"])
        _create_index_if_missing(inspector, "ix_service_settlements_created_at", "service_settlements", ["created_at"])

    if not _table_exists(inspector, "settlement_payments"):
        op.create_table(
            "settlement_payments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("service_settlements.id"), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("method", sa.String(length=50), nullable=False),
            sa.Column("reference", sa.String(length=120), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        _create_index_if_missing(inspector, "ix_settlement_payments_id", "settlement_payments", ["id"])
        _create_index_if_missing(
            inspector,
            "ix_settlement_payments_settlement_id",
            "settlement_payments",
            ["settlement_id"],
        )
        _create_index_if_missing(
            inspector,
            "ix_settlement_payments_created_at",
            "settlement_payments",
            ["created_at"],
        )

    if not _table_exists(inspector, "settlement_receipts"):
        op.create_table(
            "settlement_receipts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("settlement_id", sa.Integer(), sa.ForeignKey("service_settlements.id"), nullable=False),
            sa.Column("receipt_number", sa.String(length=40), nullable=False),
            sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("issued_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("receipt_payload", sa.JSON(), nullable=False),
        )
        _create_index_if_missing(inspector, "ix_settlement_receipts_id", "settlement_receipts", ["id"])
        _create_index_if_missing(
            inspector,
            "ix_settlement_receipts_settlement_id",
            "settlement_receipts",
            ["settlement_id"],
        )
        _create_index_if_missing(
            inspector,
            "ix_settlement_receipts_receipt_number",
            "settlement_receipts",
            ["receipt_number"],
            unique=True,
        )
        _create_index_if_missing(
            inspector,
            "ix_settlement_receipts_issued_at",
            "settlement_receipts",
            ["issued_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, indexes in [
        (
            "settlement_receipts",
            [
                "ix_settlement_receipts_issued_at",
                "ix_settlement_receipts_receipt_number",
                "ix_settlement_receipts_settlement_id",
                "ix_settlement_receipts_id",
            ],
        ),
        (
            "settlement_payments",
            [
                "ix_settlement_payments_created_at",
                "ix_settlement_payments_settlement_id",
                "ix_settlement_payments_id",
            ],
        ),
        (
            "service_settlements",
            [
                "ix_service_settlements_created_at",
                "ix_service_settlements_status",
                "ix_service_settlements_service_id",
                "ix_service_settlements_client_user_id",
                "ix_service_settlements_appointment_id",
                "ix_service_settlements_id",
            ],
        ),
    ]:
        if _table_exists(inspector, table):
            for index in indexes:
                if _index_exists(inspector, table, index):
                    op.drop_index(index, table_name=table)
            op.drop_table(table)
