"""Pydantic schemas for request/response validation and the WorkflowPlan data structures."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class ActionType(str, Enum):
    GITHUB_FETCH_PR = "github_fetch_pr"
    GITHUB_GET_REVIEWERS = "github_get_reviewers"
    GITHUB_GET_COLLABORATORS = "github_get_collaborators"
    IDENTITY_RESOLVE = "identity_resolve"
    LLM_SUMMARIZE_PR = "llm_summarize_pr"
    CALENDAR_FREEBUSY = "calendar_freebusy"
    CALENDAR_PROPOSE_SLOTS = "calendar_propose_slots"
    CALENDAR_CREATE_EVENT = "calendar_create_event"
    GMAIL_CREATE_DRAFT = "gmail_create_draft"
    GMAIL_SEND = "gmail_send"
    SLACK_POST_CHANNEL = "slack_post_channel"
    SLACK_SEND_DM = "slack_send_dm"
    LLM_DRAFT_EMAIL = "llm_draft_email"
    LLM_DRAFT_SLACK = "llm_draft_slack"
    LLM_DRAFT_DM = "llm_draft_dm"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RunStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    WAITING_FOR_CONNECTION = "waiting_for_connection"
    PARTIALLY_COMPLETED = "partially_completed"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    FAILED_RECOVERABLE = "failed_recoverable"
    SKIPPED = "skipped"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    EXPIRED = "expired"


# ──────────────────────────────────────────────
# Workflow Plan (LLM output → deterministic engine)
# ──────────────────────────────────────────────

class WorkflowStepDef(BaseModel):
    step_key: str
    action_type: ActionType
    risk_tier: RiskTier
    depends_on: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class WorkflowPlan(BaseModel):
    workflow_type: str
    steps: list[WorkflowStepDef]
    requires_slot_selection: bool = False
    requires_identity_resolution: list[str] = Field(default_factory=list)


# ──────────────────────────────────────────────
# API request / response schemas
# ──────────────────────────────────────────────

# --- User ---
class UserResponse(BaseModel):
    id: str
    auth0_user_id: str
    email: str
    name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Connected Accounts ---
class ConnectedAccountResponse(BaseModel):
    id: str
    provider: str
    status: str
    external_account_id: str | None = None
    scopes_json: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectionStartResponse(BaseModel):
    redirect_url: str


# --- Workflow Runs ---
class RunCreateRequest(BaseModel):
    prompt: str


class RunResponse(BaseModel):
    id: str
    prompt: str
    status: str
    parsed_intent_json: str | None = None
    result_summary: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StepResponse(BaseModel):
    id: str
    run_id: str
    step_key: str
    step_type: str
    risk_tier: str
    status: str
    input_json: str | None = None
    output_json: str | None = None
    error_text: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class RunDetailResponse(BaseModel):
    run: RunResponse
    steps: list[StepResponse]
    artifacts: list[ArtifactResponse] = Field(default_factory=list)


# --- Approvals ---
class ApprovalResponse(BaseModel):
    id: str
    run_id: str
    step_id: str
    approval_type: str
    target_json: str | None = None
    preview_json: str | None = None
    status: str
    ciba_auth_req_id: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Artifacts ---
class ArtifactResponse(BaseModel):
    id: str
    run_id: str
    step_id: str | None = None
    artifact_type: str
    content_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Settings ---
class SettingsRequest(BaseModel):
    default_slack_channel: str | None = None
    working_hours_start: str = "09:00"
    working_hours_end: str = "17:00"
    timezone: str = "UTC"
    default_meeting_duration_mins: int = 30
    fallback_team_json: str | None = None


class SettingsResponse(BaseModel):
    id: str
    user_id: str
    default_slack_channel: str | None = None
    working_hours_start: str
    working_hours_end: str
    timezone: str
    default_meeting_duration_mins: int
    fallback_team_json: str | None = None

    model_config = {"from_attributes": True}


# --- GitHub Repos ---
class GitHubRepoResponse(BaseModel):
    name: str
    full_name: str
    description: str | None = None
    url: str
    updated_at: str


class GitHubReposResponse(BaseModel):
    repos: list[GitHubRepoResponse]
    total: int


# --- WebSocket Events ---
class WSEvent(BaseModel):
    event: str  # 'step_update' | 'approval_required' | 'provider_action_required' | 'run_complete' | 'error'
    run_id: str
    step_id: str | None = None
    status: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


# --- Health ---
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
