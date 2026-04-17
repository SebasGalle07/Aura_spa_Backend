"""deduplicate professionals and enforce canonical names

Revision ID: 0010_professionals_canon
Revises: 0009_services_canonical_name
Create Date: 2026-04-17
"""

from __future__ import annotations

import re
import unicodedata

import sqlalchemy as sa
from alembic import op


revision = "0010_professionals_canon"
down_revision = "0009_services_canonical_name"
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
    columns = {column["name"] for column in inspector.get_columns("professionals")}
    if "canonical_name" not in columns:
        op.add_column("professionals", sa.Column("canonical_name", sa.String(length=255), nullable=True))

    professionals = bind.execute(
        sa.text("SELECT id, name, specialty, active FROM professionals ORDER BY id ASC")
    ).mappings().all()

    by_canonical: dict[str, list[dict]] = {}
    for professional in professionals:
        canonical = _canonical_text(professional["name"])
        by_canonical.setdefault(canonical, []).append(dict(professional))

    for canonical, group in by_canonical.items():
        winner = group[0]
        losers = group[1:]

        bind.execute(
            sa.text("UPDATE professionals SET canonical_name = :canonical WHERE id = :id"),
            {"canonical": canonical, "id": winner["id"]},
        )

        for loser in losers:
            if _table_exists(bind, "appointments"):
                bind.execute(
                    sa.text("UPDATE appointments SET professional_id = :winner_id WHERE professional_id = :loser_id"),
                    {"winner_id": winner["id"], "loser_id": loser["id"]},
                )
            bind.execute(sa.text("DELETE FROM professionals WHERE id = :id"), {"id": loser["id"]})

    remaining = bind.execute(sa.text("SELECT id, name FROM professionals ORDER BY id ASC")).mappings().all()
    for professional in remaining:
        bind.execute(
            sa.text("UPDATE professionals SET canonical_name = :canonical WHERE id = :id"),
            {"canonical": _canonical_text(professional["name"]), "id": professional["id"]},
        )

    op.alter_column("professionals", "canonical_name", existing_type=sa.String(length=255), nullable=False)
    op.create_index(op.f("ix_professionals_canonical_name"), "professionals", ["canonical_name"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_professionals_canonical_name"), table_name="professionals")
    op.drop_column("professionals", "canonical_name")
