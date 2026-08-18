"""learning resource system

Revision ID: 8c2df2623867
Revises: 9d909cd90180
Create Date: 2026-08-19 01:37:22.025027
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '8c2df2623867'
down_revision: str | None = '9d909cd90180'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # New enum value must be added before any column of the type is written to.
    # ADD VALUE runs outside the migration transaction (Postgres requirement).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE resource_type ADD VALUE IF NOT EXISTS 'documentation'")

    # --- resource_prerequisites (new) ------------------------------------
    op.create_table(
        "resource_prerequisites",
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column("min_proficiency", sa.Float(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("min_proficiency >= 0 AND min_proficiency <= 1", name=op.f("ck_resource_prerequisites_min_proficiency_range")),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], name=op.f("fk_resource_prerequisites_resource_id_resources"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], name=op.f("fk_resource_prerequisites_skill_id_skills"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resource_prerequisites")),
        sa.UniqueConstraint("resource_id", "skill_id", name="uq_resource_prerequisites_resource_id_skill_id"),
    )
    op.create_index(op.f("ix_resource_prerequisites_resource_id"), "resource_prerequisites", ["resource_id"], unique=False)
    op.create_index(op.f("ix_resource_prerequisites_skill_id"), "resource_prerequisites", ["skill_id"], unique=False)

    # --- resources: rename `type` -> `resource_type` (preserve data) ------
    op.alter_column("resources", "type", new_column_name="resource_type")
    op.drop_index("ix_resources_type_difficulty", table_name="resources")
    op.create_index(
        "ix_resources_resource_type_difficulty", "resources", ["resource_type", "difficulty"], unique=False
    )

    # --- resources: duration_minutes -> estimated_hours (backfill /60) ----
    op.add_column(
        "resources",
        sa.Column("estimated_hours", sa.Float(), nullable=False, server_default="0"),
    )
    op.execute("UPDATE resources SET estimated_hours = ROUND((duration_minutes / 60.0)::numeric, 2)")
    op.alter_column("resources", "estimated_hours", server_default=None)
    op.drop_constraint("duration_non_negative", "resources", type_="check")
    op.drop_column("resources", "duration_minutes")
    op.create_check_constraint("estimated_hours_non_negative", "resources", "estimated_hours >= 0")

    # --- resources: curated quality score --------------------------------
    op.add_column("resources", sa.Column("quality_score", sa.Float(), nullable=True))
    op.create_check_constraint(
        "quality_score_range", "resources", "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)"
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_constraint("quality_score_range", "resources", type_="check")
    op.drop_column("resources", "quality_score")

    op.add_column(
        "resources",
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute("UPDATE resources SET duration_minutes = ROUND(estimated_hours * 60)")
    op.alter_column("resources", "duration_minutes", server_default=None)
    op.drop_constraint("estimated_hours_non_negative", "resources", type_="check")
    op.create_check_constraint("duration_non_negative", "resources", "duration_minutes >= 0")
    op.drop_column("resources", "estimated_hours")

    # Rename the column back BEFORE rebuilding the index that references it.
    op.alter_column("resources", "resource_type", new_column_name="type")
    op.drop_index("ix_resources_resource_type_difficulty", table_name="resources")
    op.create_index("ix_resources_type_difficulty", "resources", ["type", "difficulty"], unique=False)

    op.drop_index(op.f("ix_resource_prerequisites_skill_id"), table_name="resource_prerequisites")
    op.drop_index(op.f("ix_resource_prerequisites_resource_id"), table_name="resource_prerequisites")
    op.drop_table("resource_prerequisites")
    # Note: the 'documentation' enum value is intentionally left in place;
    # Postgres cannot drop a single enum value without recreating the type.
    # ### end Alembic commands ###
