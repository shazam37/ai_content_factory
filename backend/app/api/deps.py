from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

# Re-export for use in route modules
__all__ = ["get_db"]
