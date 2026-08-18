"""Single import surface for Alembic: `Base.metadata` with every table attached."""

from app.models import Base  # noqa: F401
from app.models import *  # noqa: F401,F403

__all__ = ["Base"]
