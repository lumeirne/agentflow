"""Workflow runs API routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.schemas import RunCreateRequest, RunResponse, RunDetailResponse, StepResponse, ArtifactResponse
from backend.services.workflow_service import WorkflowService

router = APIRouter(tags=["runs"])


@router.post("/runs", response_model=RunResponse, status_code=201)
async def create_run(
    body: RunCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new workflow run from a natural-language prompt."""
    service = WorkflowService(db)
    run = await service.create_run(user_id=current_user.id, prompt=body.prompt)

    # Launch the run executor as a background task
    from backend.workers.run_executor import execute_run
    background_tasks.add_task(execute_run, run.id)

    return run


@router.get("/runs", response_model=list[RunResponse])
async def list_runs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all workflow runs for the current user."""
    service = WorkflowService(db)
    return await service.list_runs(user_id=current_user.id)


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed run info including steps and artifacts."""
    service = WorkflowService(db)
    run = await service.get_run(run_id=run_id, user_id=current_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = await service.get_run_steps(run_id=run_id)
    artifacts = await service.get_run_artifacts(run_id=run_id)

    return RunDetailResponse(
        run=RunResponse.model_validate(run),
        steps=[StepResponse.model_validate(s) for s in steps],
        artifacts=[ArtifactResponse.model_validate(a) for a in artifacts],
    )


@router.post("/runs/{run_id}/continue")
async def continue_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused run after a token reconnection."""
    service = WorkflowService(db)
    run = await service.get_run(run_id=run_id, user_id=current_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    from backend.workers.run_executor import execute_run
    background_tasks.add_task(execute_run, run.id)

    return {"status": "resumed", "run_id": run_id}
