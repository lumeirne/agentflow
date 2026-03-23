"""Approval service — create and resolve approval gates."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.approval import Approval
from backend.models.workflow_run import WorkflowRun
from backend.models.workflow_step import WorkflowStep
from backend.schemas import ApprovalStatus


class ApprovalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_approval(
        self,
        run_id: str,
        step_id: str,
        approval_type: str,
        target_json: str | None = None,
        preview_json: str | None = None,
        ciba_auth_req_id: str | None = None,
    ) -> Approval:
        """Create a new pending approval record."""
        approval = Approval(
            run_id=run_id,
            step_id=step_id,
            approval_type=approval_type,
            target_json=target_json,
            preview_json=preview_json,
            status=ApprovalStatus.PENDING.value,
            ciba_auth_req_id=ciba_auth_req_id,
        )
        self.db.add(approval)
        await self.db.flush()
        return approval

    async def resolve(
        self,
        approval_id: str,
        user_id: str,
        decision: str,
    ) -> Approval | None:
        """Approve or reject an approval gate. Returns None if not found or unauthorized."""
        result = await self.db.execute(
            select(Approval)
            .join(WorkflowRun, Approval.run_id == WorkflowRun.id)
            .where(
                Approval.id == approval_id,
                WorkflowRun.user_id == user_id,
            )
        )
        approval = result.scalar_one_or_none()
        if approval is None:
            return None

        approval.status = decision
        approval.resolved_at = datetime.now(timezone.utc)
        await self.db.flush()
        return approval

    async def list_pending(self, user_id: str) -> list[Approval]:
        """List all pending approvals for a user."""
        result = await self.db.execute(
            select(Approval)
            .join(WorkflowRun, Approval.run_id == WorkflowRun.id)
            .where(
                WorkflowRun.user_id == user_id,
                Approval.status == ApprovalStatus.PENDING.value,
            )
        )
        return list(result.scalars().all())
