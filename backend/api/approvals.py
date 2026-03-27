"""Approvals API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.schemas import ApprovalResponse
from backend.services.approval_service import ApprovalService
from backend.utils.logger import get_logger

router = APIRouter(tags=["approvals"])
logger = get_logger(__name__)


@router.get("/approvals", response_model=list[ApprovalResponse])
async def list_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all pending approvals for the current user."""
    service = ApprovalService(db)
    approvals = await service.list_pending(user_id=current_user.id)
    logger.info(
        "Listed approvals",
        extra={"data": {"user_id": current_user.id, "count": len(approvals)}},
    )
    return approvals


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
async def approve(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending approval gate."""
    logger.info(
        "Approving approval",
        extra={"data": {"approval_id": approval_id, "user_id": current_user.id}},
    )
    service = ApprovalService(db)
    approval = await service.resolve(
        approval_id=approval_id,
        user_id=current_user.id,
        decision="approved",
    )
    if approval is None:
        logger.warning(
            "Approval approve request not found",
            extra={"data": {"approval_id": approval_id, "user_id": current_user.id}},
        )
        raise HTTPException(status_code=404, detail="Approval not found")
    logger.info(
        "Approval approved",
        extra={"data": {"approval_id": approval_id, "user_id": current_user.id}},
    )
    return approval


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse)
async def reject(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending approval gate."""
    logger.info(
        "Rejecting approval",
        extra={"data": {"approval_id": approval_id, "user_id": current_user.id}},
    )
    service = ApprovalService(db)
    approval = await service.resolve(
        approval_id=approval_id,
        user_id=current_user.id,
        decision="rejected",
    )
    if approval is None:
        logger.warning(
            "Approval reject request not found",
            extra={"data": {"approval_id": approval_id, "user_id": current_user.id}},
        )
        raise HTTPException(status_code=404, detail="Approval not found")
    logger.info(
        "Approval rejected",
        extra={"data": {"approval_id": approval_id, "user_id": current_user.id}},
    )
    return approval
