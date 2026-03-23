"""Approvals API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.schemas import ApprovalResponse
from backend.services.approval_service import ApprovalService

router = APIRouter(tags=["approvals"])


@router.get("/approvals", response_model=list[ApprovalResponse])
async def list_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all pending approvals for the current user."""
    service = ApprovalService(db)
    return await service.list_pending(user_id=current_user.id)


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
async def approve(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending approval gate."""
    service = ApprovalService(db)
    approval = await service.resolve(
        approval_id=approval_id,
        user_id=current_user.id,
        decision="approved",
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse)
async def reject(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending approval gate."""
    service = ApprovalService(db)
    approval = await service.resolve(
        approval_id=approval_id,
        user_id=current_user.id,
        decision="rejected",
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval
