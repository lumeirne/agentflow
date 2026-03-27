"""Settings API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.schemas import SettingsRequest, SettingsResponse
from backend.services.settings_service import SettingsService
from backend.utils.logger import get_logger

router = APIRouter(tags=["settings"])
logger = get_logger(__name__)


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's settings (with system defaults if none exist)."""
    service = SettingsService(db)
    settings = await service.get_settings(user_id=current_user.id)
    logger.info("Fetched settings", extra={"data": {"user_id": current_user.id}})
    return settings


@router.post("/settings", response_model=SettingsResponse)
async def update_settings(
    body: SettingsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update user settings."""
    service = SettingsService(db)
    settings = await service.upsert_settings(user_id=current_user.id, data=body)
    logger.info("Updated settings", extra={"data": {"user_id": current_user.id}})
    return settings
