"""deduplicate services and enforce canonical names

Revision ID: 0009_services_canonical_name
Revises: 0008_service_settlements
Create Date: 2026-04-17
"""

from __future__ import annotations

import re
import unicodedata

import sqlalchemy as sa
from alembic import op


revision = "0009_services_canonical_name"
down_revision = "0008_service_settlements"
branch_labels = None
depends_on = None


def _canonical_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def _table_exists(connection, table_name: str) -> bool:
    return sa.inspect(connection).has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("services")}
    if "canonical_name" not in columns:
        op.add_column("services", sa.Column("canonical_name", sa.String(length=255), nullable=True))

    services = bind.execute(
        sa.text("SELECT id, name, image, active FROM services ORDER BY id ASC")
    ).mappings().all()

    by_canonical: dict[str, list[dict]] = {}
    for service in services:
        canonical = _canonical_text(service["name"])
        by_canonical.setdefault(canonical, []).append(dict(service))

    for canonical, group in by_canonical.items():
        winner = group[0]
        losers = group[1:]

        bind.execute(
            sa.text("UPDATE services SET canonical_name = :canonical WHERE id = :id"),
            {"canonical": canonical, "id": winner["id"]},
        )

        for loser in losers:
            if _table_exists(bind, "appointments"):
                bind.execute(
                    sa.text("UPDATE appointments SET service_id = :winner_id WHERE service_id = :loser_id"),
                    {"winner_id": winner["id"], "loser_id": loser["id"]},
                )
            if _table_exists(bind, "service_settlements"):
                bind.execute(
                    sa.text("UPDATE service_settlements SET service_id = :winner_id WHERE service_id = :loser_id"),
                    {"winner_id": winner["id"], "loser_id": loser["id"]},
                )

            if not winner["image"] and loser["image"]:
                bind.execute(
                    sa.text("UPDATE services SET image = :image WHERE id = :winner_id"),
                    {"image": loser["image"], "winner_id": winner["id"]},
                )
                winner["image"] = loser["image"]

            bind.execute(sa.text("DELETE FROM services WHERE id = :id"), {"id": loser["id"]})

    # Fill any rows added concurrently or with blank names before enforcing NOT NULL.
    remaining = bind.execute(sa.text("SELECT id, name FROM services ORDER BY id ASC")).mappings().all()
    for service in remaining:
        bind.execute(
            sa.text("UPDATE services SET canonical_name = :canonical WHERE id = :id"),
            {"canonical": _canonical_text(service["name"]), "id": service["id"]},
        )

    op.alter_column("services", "canonical_name", existing_type=sa.String(length=255), nullable=False)
    op.create_index(op.f("ix_services_canonical_name"), "services", ["canonical_name"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_services_canonical_name"), table_name="services")
    op.drop_column("services", "canonical_name")
