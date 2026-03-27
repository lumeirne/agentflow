"""Workflow runs API routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.auth.dependencies import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.models.connected_account import ConnectedAccount
from backend.schemas import (
    RunCreateRequest,
    RunResponse,
    RunDetailResponse,
    StepResponse,
    ArtifactResponse,
    GitHubReposResponse,
    RunStatus,
)
from backend.services.workflow_service import WorkflowService
from backend.services.github_service import github_service, TokenExpiredError
from backend.auth.token_vault import (
    ProviderConnectionMissingError,
    ProviderTokenExpiredError,
    ProviderError,
    TokenNotFoundError,
)
from backend.utils.logger import get_logger

router = APIRouter(tags=["runs"])
logger = get_logger(__name__)


@router.post("/runs", response_model=RunResponse, status_code=201)
async def create_run(
    body: RunCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new workflow run from a natural-language prompt."""
    logger.info("Creating workflow run", extra={"data": {"user_id": current_user.id}})
    service = WorkflowService(db)
    run = await service.create_run(user_id=current_user.id, prompt=body.prompt)

    from backend.workers.run_executor import execute_run
    background_tasks.add_task(execute_run, run.id)
    logger.info("Workflow run created and queued",
                extra={"data": {"user_id": current_user.id, "run_id": run.id}})
    return run


@router.get("/runs", response_model=list[RunResponse])
async def list_runs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all workflow runs for the current user."""
    service = WorkflowService(db)
    runs = await service.list_runs(user_id=current_user.id)
    logger.info("Listed workflow runs",
                extra={"data": {"user_id": current_user.id, "count": len(runs)}})
    return runs


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


@router.post("/runs/{run_id}/resume")
async def resume_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Resume a run that is waiting_for_connection after the provider has been connected.

    Only valid when run.status == waiting_for_connection and run.resume_step_id is set.
    Resets the failed_recoverable step to pending so the executor retries it.
    """
    logger.info("Resume requested", extra={"data": {"user_id": current_user.id, "run_id": run_id}})
    service = WorkflowService(db)
    run = await service.get_run(run_id=run_id, user_id=current_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != RunStatus.WAITING_FOR_CONNECTION.value:
        raise HTTPException(
            status_code=400,
            detail=f"Run is not waiting for a connection (current status: {run.status})",
        )

    if not run.resume_step_id:
        raise HTTPException(status_code=400, detail="No resume step recorded on this run")

    # Reset the failed_recoverable step to pending so executor retries it
    from backend.models.workflow_step import WorkflowStep
    from backend.schemas import StepStatus
    step_result = await db.execute(
        select(WorkflowStep).where(WorkflowStep.id == run.resume_step_id)
    )
    step = step_result.scalar_one_or_none()
    if step and step.status == StepStatus.FAILED_RECOVERABLE.value:
        step.status = StepStatus.PENDING.value
        step.error_text = None
        await db.flush()

    # Also reset any downstream skipped steps to pending so they can re-run
    all_steps_result = await db.execute(
        select(WorkflowStep)
        .where(WorkflowStep.run_id == run_id)
        .order_by(WorkflowStep.started_at)
    )
    all_steps = list(all_steps_result.scalars().all())
    found_resume = False
    for s in all_steps:
        if s.id == run.resume_step_id:
            found_resume = True
            continue
        if found_resume and s.status == StepStatus.SKIPPED.value:
            s.status = StepStatus.PENDING.value
            s.error_text = None

    await db.commit()

    from backend.workers.run_executor import execute_run
    background_tasks.add_task(execute_run, run.id)
    logger.info("Run queued for resume", extra={"data": {"run_id": run_id}})
    return {"status": "resuming", "run_id": run_id, "resume_step_id": run.resume_step_id}


@router.post("/runs/{run_id}/continue")
async def continue_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Legacy resume endpoint — delegates to execute_run."""
    service = WorkflowService(db)
    run = await service.get_run(run_id=run_id, user_id=current_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    from backend.workers.run_executor import execute_run
    background_tasks.add_task(execute_run, run.id)
    return {"status": "resumed", "run_id": run_id}


@router.get("/github/status")
async def get_github_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the GitHub connection status for the current user."""
    result = await db.execute(
        select(ConnectedAccount).where(
            (ConnectedAccount.user_id == current_user.id) &
            (ConnectedAccount.provider == "github")
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        return {"connected": False, "status": "disconnected"}
    return {"connected": account.status == "connected", "status": account.status}


@router.get("/github/repos", response_model=GitHubReposResponse)
async def get_github_repos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch list of repositories accessible to the current user's GitHub account."""
    logger.info("Fetching GitHub repositories", extra={"data": {"user_id": current_user.id}})
    result = await db.execute(
        select(ConnectedAccount).where(
            (ConnectedAccount.user_id == current_user.id) &
            (ConnectedAccount.provider == "github")
        )
    )
    github_account = result.scalar_one_or_none()

    if not github_account:
        raise HTTPException(
            status_code=400,
            detail="GitHub account not connected. Please connect your GitHub account first.",
        )

    try:
        repos = await github_service.list_user_repos(
            user_id=current_user.id,
            auth0_user_id=current_user.auth0_user_id,
        )
        return GitHubReposResponse(repos=repos, total=len(repos))
    except (ProviderConnectionMissingError, ProviderTokenExpiredError, TokenExpiredError, TokenNotFoundError) as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repositories: {e}")
