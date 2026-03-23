"""AgentState — the shared state object flowing through the LangGraph graph."""

from __future__ import annotations
from typing import Any, Optional

from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages

from backend.schemas import WorkflowStepDef


class UserSettings(TypedDict, total=False):
    default_slack_channel: str | None
    working_hours_start: str
    working_hours_end: str
    timezone: str
    default_meeting_duration_mins: int


class AgentState(TypedDict, total=False):
    """State that flows through all LangGraph nodes."""
    messages: Annotated[list, add_messages]
    user_id: str
    run_id: str
    plan: list[WorkflowStepDef]
    current_step_index: int
    tool_results: dict[str, Any]
    requires_approval: bool
    approval_status: str           # 'pending' | 'approved' | 'rejected' | 'none'
    connected_services: list[str]
    settings: UserSettings
    error: Optional[str]
