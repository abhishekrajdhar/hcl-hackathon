"""Reusable SQLAlchemy column types."""

from __future__ import annotations

from enum import Enum as PyEnum

from sqlalchemy import Enum as SAEnum


def pg_enum(enum_cls: type[PyEnum], name: str) -> SAEnum:
    """Native PostgreSQL enum that stores the *value*, not the member name."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda cls: [member.value for member in cls],
        validate_strings=True,
    )
