"""Run executor — background task that drives a workflow run to completion.

Recovery semantics
──────────────────
When a step fails due to a missing/expired provider token (ProviderConnectionMissingError
or ProviderTokenExpiredError), the step is marked `failed_recoverable`, the run is set to
`waiting_for_connection`, and a `provider_action_required` WebSocket event is emitted.

After the user connects the provider, POST /api/runs/{run_id}/resume triggers
execute_run() again. The executor detects `resume_step_id` on the run and retries
only from that step, then continues the dependency graph.

Approval suppression
────────────────────
Steps whose dependencies are failed or skipped are blocked — no approval is created
for them. This prevents phantom approvals accumulating when a run is stuck.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from backend.database import async_session_factory
from backend.services.workflow_service import WorkflowService
from backend.services.llm_service import llm_service, PlanParseError
from backend.websocket.manager import ws_manager
from backend.schemas import (
    WorkflowPlan, RunStatus, StepStatus, RiskTier, WSEvent,
)
from backend.auth.token_vault import (
    ProviderConnectionMissingError,
    ProviderTokenExpiredError,
    ProviderError,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum automatic resume attempts before requiring manual retry
MAX_AUTO_RESUME_ATTEMPTS = 1


async def execute_run(run_id: str) -> None:
    """
    Main execution loop for a workflow run.

    Handles both fresh runs and resume-from-failed-step runs.
    """
    logger.info("Run execution started", extra={"data": {"run_id": run_id}})
    async with async_session_factory() as db:
        try:
            service = WorkflowService(db)

            from sqlalchemy import select
            from backend.models.workflow_run import WorkflowRun
            from backend.models.workflow_step import WorkflowStep

            result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
            run = result.scalar_one_or_none()
            if run is None:
                logger.warning("Run not found for execution", extra={"data": {"run_id": run_id}})
                return

            user_id = run.user_id
            prompt = run.prompt
            resume_step_id: str | None = run.resume_step_id

            logger.info(
                "Loaded run for execution",
                extra={"data": {"run_id": run_id, "user_id": user_id, "resume_step_id": resume_step_id}},
            )

            # ── Planning phase (skip if resuming) ────────────────────────────
            if resume_step_id is None:
                await service.update_run_status(run_id, RunStatus.PLANNING.value)
                await _broadcast(run_id, "step_update", status="planning",
                                 data={"message": "Parsing your request..."})

                try:
                    from backend.services.settings_service import SettingsService
                    from backend.models.connected_account import ConnectedAccount

                    settings_service = SettingsService(db)
                    user_settings = await settings_service.get_settings(user_id)

                    ca_result = await db.execute(
                        select(ConnectedAccount).where(
                            (ConnectedAccount.user_id == user_id) &
                            (ConnectedAccount.status == "connected")
                        )
                    )
                    connected = [ca.provider for ca in ca_result.scalars().all()]

                    context = {
                        "connected_services": connected,
                        "settings": {
                            "default_slack_channel": user_settings.default_slack_channel,
                            "working_hours_start": user_settings.working_hours_start,
                            "working_hours_end": user_settings.working_hours_end,
                            "timezone": user_settings.timezone,
                            "default_meeting_duration_mins": user_settings.default_meeting_duration_mins,
                        },
                    }

                    plan = await llm_service.plan(prompt, context)
                    logger.info("Plan generated", extra={"data": {"run_id": run_id, "step_count": len(plan.steps)}})

                except PlanParseError as e:
                    error_msg = str(e)
                    
                    # Parse clarification requests and emit user-friendly events
                    if "clarification_needed" in error_msg.lower():
                        logger.warning(
                            "Plan generation needs clarification",
                            extra={"data": {"run_id": run_id, "clarification": error_msg}}
                        )
                        # Format clarification question for frontend
                        question = error_msg.replace("Failed to parse workflow plan: clarification_needed: ", "")
                        await service.update_run_status(run_id, RunStatus.FAILED.value, result_summary=f"Missing information: {question}")
                        await _broadcast(run_id, "clarification_needed", data={
                            "message": question,
                            "action": "Please provide the missing information or adjust your request"
                        })
                    else:
                        # Other planning errors
                        logger.error("Plan generation failed", extra={"data": {"run_id": run_id, "error": error_msg}})
                        await service.update_run_status(run_id, RunStatus.FAILED.value, result_summary=error_msg)
                        await _broadcast(run_id, "error", data={"message": error_msg})
                    
                    await db.commit()
                    return

                steps = await service.persist_plan(run_id, plan)
                await db.commit()
                logger.info("Persisted plan steps", extra={"data": {"run_id": run_id, "step_count": len(steps)}})
                await _broadcast(run_id, "step_update", status="running",
                                 data={"message": f"Executing {len(steps)} steps...", "total_steps": len(steps)})

            else:
                # ── Resume path: reload existing plan from persisted steps ──
                logger.info("Resuming run from failed step", extra={"data": {"run_id": run_id, "resume_step_id": resume_step_id}})
                await service.update_run_status(run_id, RunStatus.RUNNING.value)

                steps_result = await db.execute(
                    select(WorkflowStep)
                    .where(WorkflowStep.run_id == run_id)
                    .order_by(WorkflowStep.started_at)
                )
                steps = list(steps_result.scalars().all())

                # Rebuild plan from parsed_intent_json stored on the run
                if run.parsed_intent_json:
                    plan = WorkflowPlan.model_validate_json(run.parsed_intent_json)
                else:
                    # Fallback: re-plan (should not normally happen)
                    from backend.services.settings_service import SettingsService
                    settings_service = SettingsService(db)
                    user_settings = await settings_service.get_settings(user_id)
                    plan = await llm_service.plan(prompt, {
                        "connected_services": [],
                        "settings": {"timezone": user_settings.timezone},
                    })

                # Clear resume marker so a second resume doesn't loop
                run.resume_step_id = None
                run.waiting_provider = None
                await db.flush()

            await service.update_run_status(run_id, RunStatus.RUNNING.value)

            # ── Execute steps ─────────────────────────────────────────────────
            step_results: dict = {}

            # Pre-populate results from already-completed steps (resume path)
            for step in steps:
                if step.status == StepStatus.COMPLETED.value and step.output_json:
                    try:
                        step_results[step.step_key] = {"status": "completed", "data": json.loads(step.output_json)}
                    except Exception:
                        step_results[step.step_key] = {"status": "completed", "data": step.output_json}
                elif step.status == StepStatus.SKIPPED.value:
                    step_results[step.step_key] = {"status": "skipped"}

            for i, step in enumerate(steps):
                # Skip already-completed or skipped steps on resume
                if step.status in (StepStatus.COMPLETED.value, StepStatus.SKIPPED.value):
                    continue

                # On resume, skip steps before the failed one (they were already done)
                if resume_step_id and step.id != resume_step_id and step.status not in (
                    StepStatus.PENDING.value, StepStatus.FAILED.value, StepStatus.FAILED_RECOVERABLE.value
                ):
                    continue

                plan_step = plan.steps[i] if i < len(plan.steps) else None
                if plan_step is None:
                    continue

                logger.info(
                    "Processing step",
                    extra={"data": {"run_id": run_id, "step_id": step.id, "step_key": plan_step.step_key}},
                )

                # ── Dependency check ─────────────────────────────────────────
                should_skip = False
                for dep_key in plan_step.depends_on:
                    dep_status = step_results.get(dep_key, {}).get("status")
                    if dep_status in ("failed", "failed_recoverable", "skipped"):
                        should_skip = True
                        break

                if should_skip:
                    logger.warning(
                        "Skipping step due to failed/skipped dependency",
                        extra={"data": {"run_id": run_id, "step_id": step.id}},
                    )
                    await service.update_step_status(step.id, StepStatus.SKIPPED.value,
                                                     error_text="Dependency failed or skipped")
                    step_results[plan_step.step_key] = {"status": "skipped"}
                    await _broadcast(run_id, "step_update", step_id=step.id, status="skipped")
                    await db.commit()
                    continue

                # ── Mark running ─────────────────────────────────────────────
                await service.update_step_status(step.id, StepStatus.RUNNING.value)
                await _broadcast(run_id, "step_update", step_id=step.id, status="running",
                                 data={"step_key": plan_step.step_key, "step_index": i})
                await db.commit()

                # ── Approval gate (medium/high risk) ─────────────────────────
                if plan_step.risk_tier in (RiskTier.MEDIUM, RiskTier.HIGH):
                    await service.update_step_status(step.id, StepStatus.AWAITING_APPROVAL.value)
                    await service.update_run_status(run_id, RunStatus.WAITING_FOR_APPROVAL.value)

                    from backend.services.approval_service import ApprovalService
                    approval_service = ApprovalService(db)
                    approval = await approval_service.create_approval(
                        run_id=run_id,
                        step_id=step.id,
                        approval_type="in_app",
                        preview_json=json.dumps({
                            "action": plan_step.action_type.value,
                            "params": plan_step.params,
                            "risk_tier": plan_step.risk_tier.value,
                        }),
                    )
                    await db.commit()

                    await _broadcast(run_id, "approval_required", step_id=step.id,
                                     status="awaiting_approval",
                                     data={
                                         "approval_id": approval.id,
                                         "action": plan_step.action_type.value,
                                         "risk_tier": plan_step.risk_tier.value,
                                         "preview": plan_step.params,
                                     })
                    step_results[plan_step.step_key] = {"status": "awaiting_approval"}
                    continue

                # ── Execute low-risk step ─────────────────────────────────────
                try:
                    from backend.agent.nodes import _execute_tool
                    tool_result = await _execute_tool(plan_step, user_id, step_results)

                    result_json = json.dumps(tool_result) if not isinstance(tool_result, str) else tool_result
                    await service.update_step_status(step.id, StepStatus.COMPLETED.value, output_json=result_json)
                    step_results[plan_step.step_key] = {"status": "completed", "data": tool_result}

                    artifact_types = {
                        "llm_summarize_pr": "pr_summary",
                        "gmail_create_draft": "gmail_draft",
                        "calendar_create_event": "calendar_event",
                        "slack_post_channel": "slack_message",
                        "calendar_propose_slots": "slot_proposals",
                    }
                    if plan_step.action_type.value in artifact_types:
                        await service.create_artifact(
                            run_id=run_id,
                            step_id=step.id,
                            artifact_type=artifact_types[plan_step.action_type.value],
                            content_json=result_json,
                        )

                    await _broadcast(run_id, "step_update", step_id=step.id, status="completed")
                    logger.info("Step completed", extra={"data": {"run_id": run_id, "step_id": step.id}})

                except (ProviderConnectionMissingError, ProviderTokenExpiredError) as provider_err:
                    # ── Recoverable provider failure ──────────────────────────
                    provider = provider_err.provider
                    logger.warning(
                        "Step failed due to missing/expired provider token — pausing run",
                        extra={
                            "data": {
                                "run_id": run_id,
                                "step_id": step.id,
                                "provider": provider,
                                "error_type": type(provider_err).__name__,
                                "recoverable": True,
                                "token_source": "auth0_token_vault",
                            }
                        },
                    )
                    await service.update_step_status(
                        step.id,
                        StepStatus.FAILED_RECOVERABLE.value,
                        error_text=str(provider_err),
                    )
                    step_results[plan_step.step_key] = {"status": "failed_recoverable", "provider": provider}

                    # Store resume context on the run
                    run.resume_step_id = step.id
                    run.waiting_provider = provider
                    await db.flush()

                    await service.update_run_status(run_id, RunStatus.WAITING_FOR_CONNECTION.value)
                    await db.commit()

                    await _broadcast(
                        run_id,
                        "provider_action_required",
                        step_id=step.id,
                        status="waiting_for_connection",
                        data={
                            "provider": provider,
                            "step_id": step.id,
                            "step_key": plan_step.step_key,
                            "error": str(provider_err),
                            "recoverable": True,
                            "resume_run_id": run_id,
                        },
                    )
                    # Pause — downstream steps are blocked; mark them skipped
                    for j in range(i + 1, len(steps)):
                        downstream = steps[j]
                        if downstream.status == StepStatus.PENDING.value:
                            await service.update_step_status(
                                downstream.id, StepStatus.SKIPPED.value,
                                error_text=f"Blocked: upstream step waiting for {provider} connection"
                            )
                            if j < len(plan.steps):
                                step_results[plan.steps[j].step_key] = {"status": "skipped"}
                            await _broadcast(run_id, "step_update", step_id=downstream.id, status="skipped")
                    await db.commit()
                    return  # Pause execution here

                except Exception as e:
                    logger.error(
                        "Step execution failed",
                        extra={"data": {"run_id": run_id, "step_id": step.id, "error": str(e)}},
                    )
                    await service.update_step_status(step.id, StepStatus.FAILED.value, error_text=str(e))
                    step_results[plan_step.step_key] = {"status": "failed", "error": str(e)}
                    await _broadcast(run_id, "step_update", step_id=step.id, status="failed",
                                     data={"error": str(e)})

                await db.commit()

            # ── Final run status ──────────────────────────────────────────────
            all_statuses = [r.get("status") for r in step_results.values()]
            has_failed = "failed" in all_statuses
            has_recoverable = "failed_recoverable" in all_statuses
            has_awaiting = "awaiting_approval" in all_statuses
            has_completed = "completed" in all_statuses

            if has_awaiting:
                final_status = RunStatus.WAITING_FOR_APPROVAL.value
            elif has_recoverable:
                final_status = RunStatus.WAITING_FOR_CONNECTION.value
            elif has_failed and has_completed:
                final_status = RunStatus.PARTIALLY_COMPLETED.value
            elif has_failed:
                final_status = RunStatus.FAILED.value
            else:
                final_status = RunStatus.COMPLETED.value

            logger.info("Computed final run status", extra={"data": {"run_id": run_id, "final_status": final_status}})

            try:
                summary = await llm_service.generate_summary({"prompt": prompt, "steps": step_results})
            except Exception:
                summary = f"Workflow {'completed' if final_status == RunStatus.COMPLETED.value else 'finished with issues'}."

            await service.update_run_status(run_id, final_status, result_summary=summary)
            await db.commit()

            await _broadcast(run_id, "run_complete", status=final_status, data={"summary": summary})
            logger.info("Run execution finished", extra={"data": {"run_id": run_id, "final_status": final_status}})

        except Exception as e:
            logger.error("Unexpected run executor error", extra={"data": {"run_id": run_id, "error": str(e)}})
            try:
                service = WorkflowService(db)
                await service.update_run_status(run_id, RunStatus.FAILED.value,
                                                result_summary=f"Unexpected error: {e}")
                await db.commit()
                await _broadcast(run_id, "error", data={"message": str(e)})
            except Exception:
                pass


async def _broadcast(
    run_id: str,
    event: str,
    step_id: str | None = None,
    status: str | None = None,
    data: dict | None = None,
):
    """Helper to broadcast a WebSocket event."""
    await ws_manager.broadcast(run_id, {
        "event": event,
        "run_id": run_id,
        "step_id": step_id,
        "status": status,
        "data": data or {},
    })
