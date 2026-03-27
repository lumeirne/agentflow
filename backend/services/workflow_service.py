"""Workflow service — CRUD and lifecycle management for WorkflowRuns and WorkflowSteps."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.workflow_run import WorkflowRun
from backend.models.workflow_step import WorkflowStep
from backend.models.artifact import Artifact
from backend.schemas import WorkflowPlan, RunStatus, StepStatus, ActionType, RiskTier
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_run(self, user_id: str, prompt: str) -> WorkflowRun:
        """Create a new WorkflowRun record."""
        logger.info("Creating workflow run", extra={"data": {"user_id": user_id, "prompt_length": len(prompt)}})
        run = WorkflowRun(
            user_id=user_id,
            prompt=prompt,
            status=RunStatus.CREATED.value,
        )
        self.db.add(run)
        await self.db.flush()
        logger.info("Workflow run created", extra={"data": {"user_id": user_id, "run_id": run.id}})
        return run

    async def persist_plan(self, run_id: str, plan: WorkflowPlan) -> list[WorkflowStep]:
        """Store the parsed plan and create all WorkflowStep records (status=pending)."""
        logger.info("Persisting workflow plan", extra={"data": {"run_id": run_id, "step_count": len(plan.steps)}})
        result = await self.db.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )
        run = result.scalar_one()
        run.parsed_intent_json = plan.model_dump_json()
        run.status = RunStatus.RUNNING.value

        steps = []
        for step_def in plan.steps:
            step = WorkflowStep(
                run_id=run_id,
                step_key=step_def.step_key,
                step_type=step_def.action_type.value,
                risk_tier=step_def.risk_tier.value,
                status=StepStatus.PENDING.value,
                input_json=json.dumps(step_def.params),
            )
            self.db.add(step)
            steps.append(step)

        await self.db.flush()
        logger.info("Workflow plan persisted", extra={"data": {"run_id": run_id, "created_steps": len(steps)}})
        return steps

    async def update_step_status(
        self,
        step_id: str,
        status: str,
        output_json: str | None = None,
        error_text: str | None = None,
    ) -> WorkflowStep:
        """Update a workflow step's status and optional output/error."""
        logger.info("Updating step status", extra={"data": {"step_id": step_id, "status": status}})
        result = await self.db.execute(
            select(WorkflowStep).where(WorkflowStep.id == step_id)
        )
        step = result.scalar_one()
        step.status = status

        now = datetime.now(timezone.utc)
        if status == StepStatus.RUNNING.value:
            step.started_at = now
        if status in (StepStatus.COMPLETED.value, StepStatus.FAILED.value,
                      StepStatus.FAILED_RECOVERABLE.value, StepStatus.SKIPPED.value):
            step.completed_at = now
        if output_json is not None:
            step.output_json = output_json
        if error_text is not None:
            step.error_text = error_text

        await self.db.flush()
        return step

    async def update_run_status(self, run_id: str, status: str, result_summary: str | None = None):
        """Update the run's status and optional result summary."""
        logger.info("Updating run status", extra={"data": {"run_id": run_id, "status": status}})
        result = await self.db.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )
        run = result.scalar_one()
        run.status = status
        if result_summary is not None:
            run.result_summary = result_summary
        await self.db.flush()
        return run

    async def get_run(self, run_id: str, user_id: str) -> WorkflowRun | None:
        """Fetch a run by ID, scoped to the requesting user."""
        result = await self.db.execute(
            select(WorkflowRun).where(
                (WorkflowRun.id == run_id) &
                (WorkflowRun.user_id == user_id)
            )
        )
        return result.scalar_one_or_none()

    async def list_runs(self, user_id: str) -> list[WorkflowRun]:
        """List all runs for a user, most recent first."""
        result = await self.db.execute(
            select(WorkflowRun)
            .where(WorkflowRun.user_id == user_id)
            .order_by(WorkflowRun.created_at.desc())
        )
        runs = list(result.scalars().all())
        logger.info("Listed user runs", extra={"data": {"user_id": user_id, "count": len(runs)}})
        return runs

    async def get_run_steps(self, run_id: str) -> list[WorkflowStep]:
        """Get all steps for a given run."""
        result = await self.db.execute(
            select(WorkflowStep).where(WorkflowStep.run_id == run_id)
        )
        return list(result.scalars().all())

    async def get_run_artifacts(self, run_id: str) -> list[Artifact]:
        """Get all artifacts for a given run."""
        result = await self.db.execute(
            select(Artifact).where(Artifact.run_id == run_id)
        )
        return list(result.scalars().all())

    async def create_artifact(
        self,
        run_id: str,
        step_id: str | None,
        artifact_type: str,
        content_json: str,
    ) -> Artifact:
        """Create an artifact record."""
        logger.info(
            "Creating artifact",
            extra={"data": {"run_id": run_id, "step_id": step_id, "artifact_type": artifact_type}},
        )
        artifact = Artifact(
            run_id=run_id,
            step_id=step_id,
            artifact_type=artifact_type,
            content_json=content_json,
        )
        self.db.add(artifact)
        await self.db.flush()
        logger.info("Artifact created", extra={"data": {"artifact_id": artifact.id, "run_id": run_id}})
        return artifact

def classify_risk_tier(action_type: ActionType | str) -> RiskTier:
    """Classify an action type into a risk tier."""
    if isinstance(action_type, str):
        action_type = ActionType(action_type)
        
    low_risk = {
        ActionType.GITHUB_FETCH_PR,
        ActionType.GITHUB_GET_REVIEWERS,
        ActionType.GITHUB_GET_COLLABORATORS,
        ActionType.IDENTITY_RESOLVE,
        ActionType.LLM_SUMMARIZE_PR,
        ActionType.CALENDAR_FREEBUSY,
        ActionType.CALENDAR_PROPOSE_SLOTS,
        ActionType.GMAIL_CREATE_DRAFT,
        ActionType.LLM_DRAFT_EMAIL,
        ActionType.LLM_DRAFT_SLACK,
        ActionType.LLM_DRAFT_DM,
    }
    medium_risk = {
        ActionType.SLACK_POST_CHANNEL,
    }
    high_risk = {
        ActionType.CALENDAR_CREATE_EVENT,
        ActionType.GMAIL_SEND,
        ActionType.SLACK_SEND_DM,
    }
    
    if action_type in low_risk:
        return RiskTier.LOW
    elif action_type in medium_risk:
        return RiskTier.MEDIUM
    elif action_type in high_risk:
        return RiskTier.HIGH
    
    # Fallback to high risk for unknown actions just in case
    return RiskTier.HIGH
