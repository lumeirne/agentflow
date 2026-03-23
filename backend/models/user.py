"""User ORM model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    auth0_user_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    connected_accounts = relationship("ConnectedAccount", back_populates="user", lazy="selectin")
    settings = relationship("UserSettings", back_populates="user", uselist=False, lazy="selectin")
    workflow_runs = relationship("WorkflowRun", back_populates="user", lazy="selectin")
    identity_mappings = relationship("IdentityMapping", back_populates="user", lazy="selectin")
