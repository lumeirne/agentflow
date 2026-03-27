"""WorkflowRun ORM model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_intent_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_step_id: Mapped[str | None] = mapped_column(String, nullable=True)
    waiting_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", back_populates="workflow_runs")
    steps = relationship("WorkflowStep", back_populates="run", lazy="selectin", order_by="WorkflowStep.started_at")
    approvals = relationship("Approval", back_populates="run", lazy="selectin")
    artifacts = relationship("Artifact", back_populates="run", lazy="selectin")
