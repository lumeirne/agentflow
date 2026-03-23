"""IdentityMapping ORM model."""

import uuid

from sqlalchemy import String, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class IdentityMapping(Base):
    __tablename__ = "identity_mappings"
    __table_args__ = (
        UniqueConstraint("user_id", "github_username", name="uq_user_github"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    github_username: Mapped[str] = mapped_column(String, nullable=False)
    slack_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)

    # Relationships
    user = relationship("User", back_populates="identity_mappings")
