"""LangGraph node implementations: planner, executor, human_approval, reviewer."""

from __future__ import annotations

import json
from typing import Any

from backend.agent.state import AgentState
from backend.schemas import ActionType, RiskTier, WorkflowPlan, WorkflowStepDef
from backend.services.llm_service import llm_service, PlanParseError


# ──────────────────────────────────────────────
# Node: planner
# ──────────────────────────────────────────────

async def planner_node(state: AgentState) -> dict:
    """
    Parse user prompt into a WorkflowPlan.

    Transitions to:
      - executor  (valid plan)
      - END       (error or clarification needed)
    """
    user_prompt = ""
    for msg in reversed(state.get("messages", [])):
        if hasattr(msg, "content"):
            user_prompt = msg.content
            break

    context = {
        "connected_services": state.get("connected_services", []),
        "settings": state.get("settings", {}),
    }

    try:
        plan = await llm_service.plan(user_prompt, context)

        return {
            "plan": [step.model_dump() for step in plan.steps],
            "current_step_index": 0,
            "tool_results": {},
            "requires_approval": False,
            "approval_status": "none",
            "error": None,
        }

    except PlanParseError as e:
        return {
            "error": str(e),
            "plan": [],
        }


# ──────────────────────────────────────────────
# Node: executor
# ──────────────────────────────────────────────

async def executor_node(state: AgentState) -> dict:
    """
    Execute the current step in the plan.

    Low risk → execute directly.
    Medium/High risk → set requires_approval and transition to human_approval.
    """
    plan = state.get("plan", [])
    index = state.get("current_step_index", 0)

    if index >= len(plan):
        return {"current_step_index": index}

    step_data = plan[index]
    step = WorkflowStepDef.model_validate(step_data) if isinstance(step_data, dict) else step_data

    tool_results = dict(state.get("tool_results", {}))

    # Check dependencies
    for dep_key in step.depends_on:
        dep_result = tool_results.get(dep_key)
        if dep_result is not None and isinstance(dep_result, dict) and dep_result.get("status") == "failed":
            tool_results[step.step_key] = {"status": "skipped", "reason": f"Dependency {dep_key} failed"}
            return {
                "tool_results": tool_results,
                "current_step_index": index + 1,
                "requires_approval": False,
                "approval_status": "none",
            }

    # If medium/high risk, pause for approval
    if step.risk_tier in (RiskTier.MEDIUM, RiskTier.HIGH):
        return {
            "requires_approval": True,
            "approval_status": "pending",
        }

    # Low risk — execute directly
    try:
        result = await _execute_tool(step, state.get("user_id", ""), tool_results)
        tool_results[step.step_key] = {"status": "completed", "data": result}
    except Exception as e:
        tool_results[step.step_key] = {"status": "failed", "error": str(e)}

    return {
        "tool_results": tool_results,
        "current_step_index": index + 1,
        "requires_approval": False,
        "approval_status": "none",
    }


# ──────────────────────────────────────────────
# Node: human_approval
# ──────────────────────────────────────────────

async def human_approval_node(state: AgentState) -> dict:
    """
    Pause for user approval on medium/high risk steps.
    This node is resumed after the user approves or rejects.
    """
    plan = state.get("plan", [])
    index = state.get("current_step_index", 0)
    approval_status = state.get("approval_status", "pending")
    tool_results = dict(state.get("tool_results", {}))

    if index >= len(plan):
        return {"requires_approval": False, "approval_status": "none"}

    step_data = plan[index]
    step = WorkflowStepDef.model_validate(step_data) if isinstance(step_data, dict) else step_data

    if approval_status == "approved":
        try:
            result = await _execute_tool(step, state.get("user_id", ""), tool_results)
            tool_results[step.step_key] = {"status": "completed", "data": result}
        except Exception as e:
            tool_results[step.step_key] = {"status": "failed", "error": str(e)}

        return {
            "tool_results": tool_results,
            "current_step_index": index + 1,
            "requires_approval": False,
            "approval_status": "none",
        }

    elif approval_status == "rejected":
        tool_results[step.step_key] = {"status": "skipped", "reason": "User rejected"}
        return {
            "tool_results": tool_results,
            "current_step_index": index + 1,
            "requires_approval": False,
            "approval_status": "none",
        }

    # Still pending — this should not normally happen in a resumed flow
    return {"requires_approval": True, "approval_status": "pending"}


# ──────────────────────────────────────────────
# Node: reviewer
# ──────────────────────────────────────────────

async def reviewer_node(state: AgentState) -> dict:
    """
    Final node — generate a result summary for the completed run.
    """
    tool_results = state.get("tool_results", {})

    summary_context = {
        "run_id": state.get("run_id", ""),
        "steps": tool_results,
    }

    try:
        summary = await llm_service.generate_summary(summary_context)
    except Exception:
        summary = "Workflow completed. Check individual step results for details."

    return {"error": None}


# ──────────────────────────────────────────────
# Tool dispatcher
# ──────────────────────────────────────────────

async def _execute_tool(step: WorkflowStepDef, user_id: str, tool_results: dict) -> Any:
    """Dispatch to the correct tool function based on action_type."""
    action = step.action_type
    params = step.params

    if action == ActionType.GITHUB_FETCH_PR:
        from backend.tools.github_tools import github_get_latest_pr
        return await github_get_latest_pr(user_id, params.get("repo", ""))

    elif action == ActionType.GITHUB_GET_REVIEWERS:
        from backend.tools.github_tools import github_get_pr_reviewers
        pr_data = tool_results.get("github_fetch_pr", {}).get("data", {})
        pr_number = params.get("pr_number") or pr_data.get("number")
        return await github_get_pr_reviewers(user_id, params.get("repo", ""), pr_number)

    elif action == ActionType.GITHUB_GET_COLLABORATORS:
        from backend.tools.github_tools import github_get_repo_collaborators
        return await github_get_repo_collaborators(user_id, params.get("repo", ""))

    elif action == ActionType.LLM_SUMMARIZE_PR:
        pr_data = tool_results.get("github_fetch_pr", {}).get("data", {})
        return await llm_service.summarize_pr(pr_data)

    elif action == ActionType.LLM_DRAFT_EMAIL:
        return await llm_service.draft_email({"tool_results": tool_results, **params})

    elif action == ActionType.LLM_DRAFT_SLACK:
        return await llm_service.draft_slack({"tool_results": tool_results, **params})

    elif action == ActionType.LLM_DRAFT_DM:
        recipient = params.get("recipient", "")
        return await llm_service.draft_dm({"tool_results": tool_results, **params}, recipient)

    elif action == ActionType.CALENDAR_FREEBUSY:
        from backend.tools.google_tools import calendar_check_freebusy
        return await calendar_check_freebusy(
            user_id,
            params.get("attendee_emails", []),
            params.get("time_min", ""),
            params.get("time_max", ""),
            params.get("timezone", "UTC"),
        )

    elif action == ActionType.CALENDAR_PROPOSE_SLOTS:
        from backend.tools.google_tools import calendar_propose_slots
        freebusy = tool_results.get("calendar_freebusy", {}).get("data", {})
        return await calendar_propose_slots(freebusy)

    elif action == ActionType.CALENDAR_CREATE_EVENT:
        from backend.tools.google_tools import calendar_create_event
        return await calendar_create_event(user_id, params.get("event_payload", {}))

    elif action == ActionType.GMAIL_CREATE_DRAFT:
        from backend.tools.google_tools import gmail_create_draft
        draft = params.get("draft", {})
        return await gmail_create_draft(user_id, draft.get("to", []), draft.get("subject", ""), draft.get("body", ""))

    elif action == ActionType.GMAIL_SEND:
        from backend.tools.google_tools import gmail_send_message
        draft_id = params.get("draft_id") or tool_results.get("gmail_create_draft", {}).get("data", "")
        return await gmail_send_message(user_id, draft_id)

    elif action == ActionType.SLACK_POST_CHANNEL:
        from backend.tools.slack_tools import slack_post_channel_message
        return await slack_post_channel_message(
            user_id,
            params.get("channel_id", ""),
            params.get("blocks", []),
            params.get("text", ""),
        )

    elif action == ActionType.SLACK_SEND_DM:
        from backend.tools.slack_tools import slack_send_dm
        return await slack_send_dm(user_id, params.get("slack_user_id", ""), params.get("text", ""))

    elif action == ActionType.IDENTITY_RESOLVE:
        from backend.tools.utility_tools import resolve_team_members
        return await resolve_team_members(params.get("github_usernames", []), user_id, None)

    else:
        raise ValueError(f"Unknown action type: {action}")
