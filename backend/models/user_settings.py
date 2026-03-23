"""UserSettings ORM model."""

import uuid

from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), unique=True, nullable=False)
    default_slack_channel: Mapped[str | None] = mapped_column(String, nullable=True)
    working_hours_start: Mapped[str] = mapped_column(String, default="09:00")
    working_hours_end: Mapped[str] = mapped_column(String, default="17:00")
    timezone: Mapped[str] = mapped_column(String, default="UTC")
    default_meeting_duration_mins: Mapped[int] = mapped_column(Integer, default=30)
    fallback_team_json: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    user = relationship("User", back_populates="settings")
