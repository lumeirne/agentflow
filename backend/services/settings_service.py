"""Settings service — manage user preferences with system defaults."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user_settings import UserSettings
from backend.schemas import SettingsRequest


class SettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_settings(self, user_id: str) -> UserSettings:
        """Return user settings, creating a record with system defaults if none exists."""
        result = await self.db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()

        if settings is None:
            settings = UserSettings(user_id=user_id)
            self.db.add(settings)
            await self.db.flush()

        return settings

    async def upsert_settings(self, user_id: str, data: SettingsRequest) -> UserSettings:
        """Create or update user settings."""
        result = await self.db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()

        if settings is None:
            settings = UserSettings(user_id=user_id)
            self.db.add(settings)

        settings.default_slack_channel = data.default_slack_channel
        settings.working_hours_start = data.working_hours_start
        settings.working_hours_end = data.working_hours_end
        settings.timezone = data.timezone
        settings.default_meeting_duration_mins = data.default_meeting_duration_mins
        settings.fallback_team_json = data.fallback_team_json

        await self.db.flush()
        return settings
