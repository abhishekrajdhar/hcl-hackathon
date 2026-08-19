"""allow milestone_review path items without a resource or assessment

Revision ID: 8165319377d1
Revises: 8c2df2623867
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "8165319377d1"
down_revision: str | None = "8c2df2623867"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = "resource_id IS NOT NULL OR assessment_id IS NOT NULL"
_NEW = (
    "resource_id IS NOT NULL OR assessment_id IS NOT NULL "
    "OR item_type = 'milestone_review'"
)


def upgrade() -> None:
    op.drop_constraint(
        "item_targets_resource_or_assessment", "learning_path_items", type_="check"
    )
    op.create_check_constraint(
        "item_targets_resource_or_assessment", "learning_path_items", _NEW
    )


def downgrade() -> None:
    op.drop_constraint(
        "item_targets_resource_or_assessment", "learning_path_items", type_="check"
    )
    op.create_check_constraint(
        "item_targets_resource_or_assessment", "learning_path_items", _OLD
    )
