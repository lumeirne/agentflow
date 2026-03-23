"""Settings API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.schemas import SettingsRequest, SettingsResponse
from backend.services.settings_service import SettingsService

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's settings (with system defaults if none exist)."""
    service = SettingsService(db)
    return await service.get_settings(user_id=current_user.id)


@router.post("/settings", response_model=SettingsResponse)
async def update_settings(
    body: SettingsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update user settings."""
    service = SettingsService(db)
    return await service.upsert_settings(user_id=current_user.id, data=body)
