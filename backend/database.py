"""Async SQLAlchemy engine, session factory, and DB initialisation."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields a session and closes it after the request."""
    async with async_session_factory() as session:
        logger.info("DB session opened")
        try:
            yield session
            await session.commit()
            logger.info("DB session committed")
        except Exception as e:
            await session.rollback()
            logger.error("DB session rolled back", extra={"data": {"error": str(e)}})
            raise
        finally:
            await session.close()
            logger.info("DB session closed")


async def init_db() -> None:
    """Create all tables that don't already exist."""
    logger.info("Initializing database metadata")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database metadata initialization completed")
