"""add coding and conceptual question types

Revision ID: c4134c446695
Revises: 8165319377d1
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c4134c446695"
down_revision: str | None = "8165319377d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE question_type ADD VALUE IF NOT EXISTS 'coding'")
        op.execute("ALTER TYPE question_type ADD VALUE IF NOT EXISTS 'conceptual'")


def downgrade() -> None:
    # Postgres cannot drop a single enum value; left in place intentionally.
    pass
