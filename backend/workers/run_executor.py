"""Run executor — background task that drives a workflow run to completion."""

import json
from datetime import datetime, timezone

from backend.database import async_session_factory
from backend.services.workflow_service import WorkflowService
from backend.services.llm_service import llm_service, PlanParseError
from backend.websocket.manager import ws_manager
from backend.schemas import (
    WorkflowPlan, RunStatus, StepStatus, RiskTier, WSEvent,
)


async def execute_run(run_id: str) -> None:
    """
    Main execution loop for a workflow run.

    1. Load the run record
    2. Parse the prompt into a WorkflowPlan via LLM
    3. Persist all steps (status=pending)
    4. Execute each step sequentially:
       - Low risk  → execute tool directly
       - Med/High  → create approval, pause, wait
    5. Update run status on completion
    """
    async with async_session_factory() as db:
        try:
            service = WorkflowService(db)

            # ── Load run ──
            from sqlalchemy import select
            from backend.models.workflow_run import WorkflowRun

            result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
            run = result.scalar_one_or_none()
            if run is None:
                return

            user_id = run.user_id
            prompt = run.prompt

            # ── Planning phase ──
            await service.update_run_status(run_id, RunStatus.PLANNING.value)
            await _broadcast(run_id, "step_update", status="planning", data={"message": "Parsing your request..."})

            try:
                # Build context for planner
                from backend.services.settings_service import SettingsService
                from backend.models.connected_account import ConnectedAccount

                settings_service = SettingsService(db)
                user_settings = await settings_service.get_settings(user_id)

                ca_result = await db.execute(
                    select(ConnectedAccount).where(
                        ConnectedAccount.user_id == user_id,
                        ConnectedAccount.status == "connected",
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

            except PlanParseError as e:
                await service.update_run_status(run_id, RunStatus.FAILED.value, result_summary=str(e))
                await _broadcast(run_id, "error", data={"message": str(e)})
                await db.commit()
                return

            # ── Persist steps ──
            steps = await service.persist_plan(run_id, plan)
            await db.commit()

            await _broadcast(run_id, "step_update", status="running",
                             data={"message": f"Executing {len(steps)} steps...", "total_steps": len(steps)})

            # ── Execute steps ──
            step_results: dict = {}

            for i, step in enumerate(steps):
                # Check dependencies
                plan_step = plan.steps[i]
                should_skip = False
                for dep_key in plan_step.depends_on:
                    dep_status = step_results.get(dep_key, {}).get("status")
                    if dep_status == "failed":
                        should_skip = True
                        break

                if should_skip:
                    await service.update_step_status(step.id, StepStatus.SKIPPED.value,
                                                     error_text=f"Dependency failed")
                    step_results[plan_step.step_key] = {"status": "skipped"}
                    await _broadcast(run_id, "step_update", step_id=step.id, status="skipped")
                    await db.commit()
                    continue

                # Mark as running
                await service.update_step_status(step.id, StepStatus.RUNNING.value)
                await _broadcast(run_id, "step_update", step_id=step.id, status="running",
                                 data={"step_key": plan_step.step_key, "step_index": i})
                await db.commit()

                # Check risk tier
                if plan_step.risk_tier in (RiskTier.MEDIUM, RiskTier.HIGH):
                    # Create approval and pause
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

                    # The run is now paused. The approval API endpoint will
                    # update the approval status. A separate mechanism (e.g.,
                    # polling or resume endpoint) continues execution.
                    step_results[plan_step.step_key] = {"status": "awaiting_approval"}
                    continue

                # Low risk — execute directly
                try:
                    from backend.agent.nodes import _execute_tool
                    tool_result = await _execute_tool(plan_step, user_id, step_results)

                    result_json = json.dumps(tool_result) if not isinstance(tool_result, str) else tool_result
                    await service.update_step_status(step.id, StepStatus.COMPLETED.value, output_json=result_json)
                    step_results[plan_step.step_key] = {"status": "completed", "data": tool_result}

                    # Store artifact if applicable
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

                except Exception as e:
                    await service.update_step_status(step.id, StepStatus.FAILED.value, error_text=str(e))
                    step_results[plan_step.step_key] = {"status": "failed", "error": str(e)}
                    await _broadcast(run_id, "step_update", step_id=step.id, status="failed",
                                     data={"error": str(e)})

                await db.commit()

            # ── Determine final run status ──
            all_statuses = [r.get("status") for r in step_results.values()]
            has_failed = "failed" in all_statuses
            has_awaiting = "awaiting_approval" in all_statuses
            has_completed = "completed" in all_statuses

            if has_awaiting:
                final_status = RunStatus.WAITING_FOR_APPROVAL.value
            elif has_failed and has_completed:
                final_status = RunStatus.PARTIALLY_COMPLETED.value
            elif has_failed:
                final_status = RunStatus.FAILED.value
            else:
                final_status = RunStatus.COMPLETED.value

            # Generate summary
            try:
                summary = await llm_service.generate_summary({
                    "prompt": prompt,
                    "steps": step_results,
                })
            except Exception:
                summary = f"Workflow {'completed' if final_status == 'completed' else 'finished with issues'}."

            await service.update_run_status(run_id, final_status, result_summary=summary)
            await db.commit()

            await _broadcast(run_id, "run_complete", status=final_status,
                             data={"summary": summary})

        except Exception as e:
            # Catch-all: mark the run as failed
            try:
                service = WorkflowService(db)
                await service.update_run_status(run_id, RunStatus.FAILED.value, result_summary=f"Unexpected error: {e}")
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
