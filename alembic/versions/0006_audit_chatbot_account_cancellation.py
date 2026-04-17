"""audit logs, chatbot, and account cancellation requests

Revision ID: 0006_audit_support
Revises: 0005_reservation_workflow
Create Date: 2026-04-15 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_audit_support"
down_revision = "0005_reservation_workflow"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _create_index_if_missing(inspector, name: str, table: str, columns: list[str]) -> None:
    if not _index_exists(inspector, table, name):
        op.create_index(name, table, columns, unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _column_exists(inspector, "users", "is_active"):
        op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
        op.alter_column("users", "is_active", server_default=None)
    if not _column_exists(inspector, "users", "deactivated_at"):
        op.add_column("users", sa.Column("deactivated_at", sa.DateTime(), nullable=True))

    if not _table_exists(inspector, "audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("actor_role", sa.String(length=32), nullable=True),
            sa.Column("action", sa.String(length=120), nullable=False),
            sa.Column("entity_type", sa.String(length=80), nullable=False),
            sa.Column("entity_id", sa.String(length=80), nullable=True),
            sa.Column("old_value", sa.JSON(), nullable=True),
            sa.Column("new_value", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.String(length=80), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        _create_index_if_missing(inspector, "ix_audit_logs_id", "audit_logs", ["id"])
        _create_index_if_missing(inspector, "ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
        _create_index_if_missing(inspector, "ix_audit_logs_action", "audit_logs", ["action"])
        _create_index_if_missing(inspector, "ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
        _create_index_if_missing(inspector, "ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
        _create_index_if_missing(inspector, "ix_audit_logs_created_at", "audit_logs", ["created_at"])

    if not _table_exists(inspector, "account_cancellation_requests"):
        op.create_table(
            "account_cancellation_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("admin_response", sa.Text(), nullable=True),
            sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        _create_index_if_missing(
            inspector,
            "ix_account_cancellation_requests_id",
            "account_cancellation_requests",
            ["id"],
        )
        _create_index_if_missing(
            inspector,
            "ix_account_cancellation_requests_user_id",
            "account_cancellation_requests",
            ["user_id"],
        )
        _create_index_if_missing(
            inspector,
            "ix_account_cancellation_requests_status",
            "account_cancellation_requests",
            ["status"],
        )
        _create_index_if_missing(
            inspector,
            "ix_account_cancellation_requests_created_at",
            "account_cancellation_requests",
            ["created_at"],
        )

    if not _table_exists(inspector, "chatbot_conversations"):
        op.create_table(
            "chatbot_conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        _create_index_if_missing(inspector, "ix_chatbot_conversations_id", "chatbot_conversations", ["id"])
        _create_index_if_missing(inspector, "ix_chatbot_conversations_user_id", "chatbot_conversations", ["user_id"])
        _create_index_if_missing(inspector, "ix_chatbot_conversations_status", "chatbot_conversations", ["status"])
        _create_index_if_missing(
            inspector,
            "ix_chatbot_conversations_created_at",
            "chatbot_conversations",
            ["created_at"],
        )

    if not _table_exists(inspector, "chatbot_messages"):
        op.create_table(
            "chatbot_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("chatbot_conversations.id"), nullable=False),
            sa.Column("sender", sa.String(length=32), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        _create_index_if_missing(inspector, "ix_chatbot_messages_id", "chatbot_messages", ["id"])
        _create_index_if_missing(
            inspector,
            "ix_chatbot_messages_conversation_id",
            "chatbot_messages",
            ["conversation_id"],
        )
        _create_index_if_missing(inspector, "ix_chatbot_messages_created_at", "chatbot_messages", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, indexes in [
        ("chatbot_messages", ["ix_chatbot_messages_created_at", "ix_chatbot_messages_conversation_id", "ix_chatbot_messages_id"]),
        (
            "chatbot_conversations",
            [
                "ix_chatbot_conversations_created_at",
                "ix_chatbot_conversations_status",
                "ix_chatbot_conversations_user_id",
                "ix_chatbot_conversations_id",
            ],
        ),
        (
            "account_cancellation_requests",
            [
                "ix_account_cancellation_requests_created_at",
                "ix_account_cancellation_requests_status",
                "ix_account_cancellation_requests_user_id",
                "ix_account_cancellation_requests_id",
            ],
        ),
        (
            "audit_logs",
            [
                "ix_audit_logs_created_at",
                "ix_audit_logs_entity_id",
                "ix_audit_logs_entity_type",
                "ix_audit_logs_action",
                "ix_audit_logs_actor_user_id",
                "ix_audit_logs_id",
            ],
        ),
    ]:
        if _table_exists(inspector, table):
            for index in indexes:
                if _index_exists(inspector, table, index):
                    op.drop_index(index, table_name=table)
            op.drop_table(table)

    if _column_exists(inspector, "users", "deactivated_at"):
        op.drop_column("users", "deactivated_at")
    if _column_exists(inspector, "users", "is_active"):
        op.drop_column("users", "is_active")
