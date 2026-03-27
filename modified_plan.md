## Plan: Auth0 Token Vault-First Workflow + In-Page Provider Recovery

Replace DB-backed provider token handling with Auth0 Token Vault-only retrieval, then unify workflow/backend/frontend behavior so missing GitHub/Google/Slack connections are resolved inline during run execution (hybrid fallback to Connections page), with recoverable pause/resume semantics and approval/dependency correctness.

**Steps**
1. Phase 1 - Auth0 Token Vault Foundation (blocking)
1.1 Add Token Vault-specific config and provider mapping in backend settings and auth client internals: Auth0 domain/client credentials, custom API client credentials for token exchange, My Account API audience/scopes, provider connection aliases (github, google-oauth2, slack/sign-in-with-slack). *blocks all later backend steps*
1.2 Refactor token retrieval in token vault client to Auth0-only strategy: remove DB token read path and DB token write path for provider credentials; keep only Auth0 token exchange/retrieval flow and explicit typed errors for missing connection vs expired/unauthorized vs transient Auth0 errors.
1.3 Align connection initiation/completion to Connected Accounts semantics (My Account API connect/complete-compatible behavior), while preserving current app callback wiring; persist only metadata needed for UX/reporting (connection id/status/scopes), never provider access tokens.
1.4 Add structured error taxonomy used across services: `ProviderConnectionMissingError`, `ProviderTokenExpiredError`, `ProviderTokenExchangeError`, `ProviderTemporaryError` for deterministic workflow branching.
2. Phase 2 - Provider Services and Tool Layer Hardening (depends on Phase 1; parallelizable per provider)
2.1 Update GitHub service calls (including repo list endpoint path) to request token only from Auth0 Token Vault client and surface typed errors with provider name and recoverability hints.
2.2 Update Google Calendar/Gmail service calls to same typed-error behavior and token source rules.
2.3 Update Slack service calls similarly; normalize connection name differences between UI provider key and Auth0 connection strategy.
2.4 Update tool wrappers and dispatcher so all provider tool executions propagate typed provider errors unchanged to executor (no generic wrapping that hides recoverability).
3. Phase 3 - Workflow Engine Correctness and Recovery (depends on Phases 1-2)
3.1 Add preflight run validation at run creation/planning boundary: infer required providers from planned actions (not just prompt keywords) and detect missing connected accounts before execution starts.
3.2 Add recoverable pause state for provider-missing failures: when a step fails due to missing/expired provider token, mark step failed-recoverable, mark run waiting_for_connection, and emit websocket action-required payload containing provider, step id, and resume token/context.
3.3 Implement resume-from-failed-step path after successful connection: retry only the failed step and then continue dependency graph, with idempotency safeguards.
3.4 Fix dependency and approval control flow: downstream steps must be blocked when dependencies are failed or skipped; suppress approval creation for blocked steps; stop creating additional approvals once run is blocked by dependency/provider state.
3.5 Ensure final run status computation distinguishes terminal failure vs recoverable waiting state vs partially completed.
4. Phase 4 - In-Page Hybrid Connection UX (depends on Phase 3 websocket contract; frontend/backend can partially parallelize after event schema is finalized)
4.1 Extend run detail page to handle provider action-required events and show inline connect prompt/modal for GitHub/Google/Slack without forcing settings navigation.
4.2 Reuse/extend connection start/callback flow from Connections page for in-run invocation; after callback success, return to originating run page and auto-trigger resume endpoint for failed step.
4.3 Keep hybrid fallback path: expose secondary action to open Connections page if popup/redirect fails; when connection is completed there, return to run with pending-resume context preserved.
4.4 Extend global/frontend state and websocket handling to represent states: `missing_provider`, `connecting_provider`, `connection_restored`, `resuming_step`, `resume_failed`.
4.5 Add per-step UI affordances: recoverable failure badges, provider-specific reconnect button, and clear messaging that no full rerun is required unless user chooses.
5. Phase 5 - Compatibility, Data, and Migration Safety (parallel with late Phase 4 UI polishing)
5.1 Create migration path for existing connected account rows: preserve status/provider metadata, ignore/remove encrypted token fields in runtime logic, and optionally backfill connection metadata from Auth0 connected accounts endpoint.
5.2 Add telemetry/logging changes for auditability: explicit log fields for token source=`auth0_token_vault`, provider, error_type, recoverable, resume_attempt.
5.3 Add feature flags for staged rollout (optional but recommended): token-vault-only enforcement and in-run connect UX toggles.
6. Phase 6 - Verification and Release Readiness (depends on all previous phases)
6.1 Unit tests for token vault client, service adapters, and typed error propagation.
6.2 Workflow integration tests for full happy path and recovery cases across GitHub, Google, Slack.
6.3 UI interaction tests for in-run connect flow (connect success, cancel, callback fail, resume fail, retry success).
6.4 Manual end-to-end scenarios in local/dev tenant with real Auth0 config and connected accounts.
6.5 Release checklist for Auth0 tenant prerequisites and environment variables to prevent false negatives.

**Relevant files**
- d:/Doc/auth0_hackathon/backend/auth/token_vault.py — replace DB-first token logic with Auth0 Token Vault-only retrieval, connected-accounts-compatible flow, and typed provider errors
- d:/Doc/auth0_hackathon/backend/config.py — add Auth0 Token Vault/Custom API client/My Account API settings
- d:/Doc/auth0_hackathon/backend/api/auth.py — align connect/callback semantics to connected accounts metadata lifecycle (no DB token storage)
- d:/Doc/auth0_hackathon/backend/api/runs.py — preflight provider requirement checks and resume endpoints
- d:/Doc/auth0_hackathon/backend/workers/run_executor.py — recoverable provider-missing pause/resume, dependency/approval suppression, status correctness
- d:/Doc/auth0_hackathon/backend/agent/nodes.py — typed error propagation from tool execution
- d:/Doc/auth0_hackathon/backend/services/github_service.py — token source enforcement for repo listing + PR actions
- d:/Doc/auth0_hackathon/backend/services/google_service.py — token source enforcement for calendar/gmail actions
- d:/Doc/auth0_hackathon/backend/services/slack_service.py — token source enforcement for slack actions
- d:/Doc/auth0_hackathon/backend/tools/github_tools.py — typed error pass-through
- d:/Doc/auth0_hackathon/backend/tools/google_tools.py — typed error pass-through
- d:/Doc/auth0_hackathon/backend/tools/slack_tools.py — typed error pass-through
- d:/Doc/auth0_hackathon/backend/models/connected_account.py — metadata-only persistence expectations and migration alignment
- d:/Doc/auth0_hackathon/frontend/app/runs/[id]/page.tsx — inline provider connection and resume UX
- d:/Doc/auth0_hackathon/frontend/hooks/useWebSocket.ts — new provider action-required event handling/state transitions
- d:/Doc/auth0_hackathon/frontend/lib/store.ts — run recovery state model for provider reconnect/resume
- d:/Doc/auth0_hackathon/frontend/components/StepCard.tsx — recoverable provider failure affordances and reconnect CTA
- d:/Doc/auth0_hackathon/frontend/app/connections/page.tsx — shared initiation/callback compatibility with in-run flow
- d:/Doc/auth0_hackathon/frontend/app/api/connections/[provider]/start/route.ts — support return-to-run context in connect start
- d:/Doc/auth0_hackathon/frontend/app/api/connections/[provider]/callback/route.ts — route back to originating run and emit resume trigger data

**Verification**
1. Automated backend tests: token retrieval uses only Auth0 Token Vault path and never DB token columns.
2. Automated backend tests: repo fetch (`/api/github/repos`) and workflow `github_fetch_pr` both succeed with same Auth0 Token Vault token source.
3. Automated backend tests: missing GitHub/Google/Slack triggers recoverable waiting state, not terminal failure.
4. Automated backend tests: dependency skip and approval suppression behave correctly when upstream step fails/skips.
5. Automated frontend tests: run page opens in-page connect prompt for missing provider and resumes from failed step after callback.
6. Manual scenario: start run requiring GitHub when disconnected; connect in-page; run resumes and continues without full restart.
7. Manual scenario: Google token expires mid-run; reconnect in-page; only failed step retries; downstream steps proceed.
8. Manual scenario: Slack missing while approval step exists; blocked approvals are not created for steps with failed/skipped dependencies.
9. Log validation: every provider API call logs token source as Auth0 Token Vault and emits provider-specific recoverability metadata.

**Decisions**
- Connection UX: hybrid. Primary is in-page connect/recover; fallback link to Connections page remains.
- Run behavior: pause and resume from failed step after provider connection is restored.
- Token source strictness: Auth0 Token Vault only; remove DB token fallback.
- Provider scope: implement for GitHub, Google, and Slack in this scope.
- Approval policy: suppress approvals for steps blocked by failed/skipped dependencies.

**Further Considerations**
1. Auth0 tenant readiness gate: add startup self-check endpoint/health warning to validate My Account API, MRRT, and Token Vault grant are enabled before allowing runs.
2. Recovery retry policy: choose max auto-resume attempts (recommended: 1 automatic + manual retries thereafter) to avoid infinite loops.
3. Backward compatibility window: keep encrypted token columns for one release but mark unused, then remove in later migration once stable.
