"""LLM prompt templates for the planner, summarizer, and drafting nodes."""

from backend.schemas import ActionType, RiskTier


def get_planner_prompt(context: dict) -> str:
    """System prompt for the planner node."""
    connected = context.get("connected_services", [])
    settings = context.get("settings", {})

    action_types = [a.value for a in ActionType]
    risk_tiers = [r.value for r in RiskTier]
    
    default_slack = settings.get('default_slack_channel')

    return f"""You are AgentFlow's planning engine. Your job is to parse a user's natural-language request and produce a structured JSON workflow plan.

## Connected Services
The user has connected: {', '.join(connected) if connected else 'none'}

## User Settings
- Default Slack channel: {default_slack or '(none - not set)'}
- Meeting duration: {settings.get('default_meeting_duration_mins', 30)} minutes
- Working hours: {settings.get('working_hours_start', '09:00')} – {settings.get('working_hours_end', '17:00')} {settings.get('timezone', 'UTC')}

## Valid Action Types
{', '.join(action_types)}

## Risk Tier Rules
- LOW: github_fetch_pr, github_get_reviewers, github_get_collaborators, identity_resolve, llm_summarize_pr, calendar_freebusy, calendar_propose_slots, gmail_create_draft, llm_draft_email, llm_draft_slack, llm_draft_dm
- MEDIUM: slack_post_channel
- HIGH: calendar_create_event, gmail_send, slack_send_dm

## Output Format
Return ONLY valid JSON matching this schema (no extra text):
{{
  "workflow_type": "<string describing the workflow>",
  "steps": [
    {{
      "step_key": "<unique identifier>",
      "action_type": "<one of the valid action types>",
      "risk_tier": "<low|medium|high>",
      "depends_on": ["<dependencies>"],
      "params": {{<extracted parameters>}}
    }}
  ],
  "requires_slot_selection": <true if scheduling needed>,
  "requires_identity_resolution": []
}}

## CRITICAL Rules
1. **ALWAYS generate a plan** - do NOT ask for clarifications unless repository is completely missing
2. **For Slack messages**: Use the default_slack_channel if set. If not set, skip slack steps.
3. **For email recipients**: If explicit email addresses mentioned (user@example.com), use them. Otherwise use empty array [] - approval steps will ask.
4. **For meeting attendees**: If mentioned in prompt, extract them. Otherwise use empty array [] - user can add during scheduling.
5. **Repository is REQUIRED**: Only ask for clarification if repo is completely missing from the prompt.
6. **Always include these steps** when applicable:
   - github_fetch_pr (if repo + PR review requested)
   - llm_summarize_pr (if fetching PR)
   - llm_draft_email (if email needed - even if recipients TBD - will need approval)
   - llm_draft_slack (if Slack post needed)
   - gmail_send (HIGH risk - will need approval first)
   - slack_post_channel (MEDIUM risk - may need approval)
7. Use risk_tier strictly per the rules above
8. Include all dependency relationships
9. Never hallucinate email addresses or attendees - extract or use empty arrays

## Example: User says "Review PR and send to team"
- Extract repo if mentioned
- If no specific emails: recipients = []
- If no meeting requested: skip calendar steps
- Plan should NOT fail - approval steps will ask for email details
"""


def get_summarizer_prompt() -> str:
    """System prompt for PR summarization."""
    return """You are a technical writer. Given a GitHub pull request JSON object, produce a concise plain-English summary with:

1. **What changed** (2-3 sentences)
2. **Why it matters** (1-2 sentences)
3. **Risks or open questions** (bullet points, if any)
4. **Suggested meeting agenda** (2-3 bullet points)

Keep it professional, clear, and suitable for inclusion in calendar invites and emails.
Do NOT include raw JSON or code — this is for non-technical stakeholders too."""


def get_drafting_prompt(draft_type: str) -> str:
    """System prompt for content drafting (email, slack, dm)."""
    prompts = {
        "email": """You are drafting a professional meeting notification email. Given context (PR summary, meeting details, attendees), produce JSON:
{{
  "subject": "<clear subject line referencing the PR>",
  "body": "<formatted email body with meeting details, PR summary, and agenda>",
  "to": ["<attendee emails>"]
}}
Keep the tone professional but friendly. Include the meeting time, location/link, and a brief PR summary.""",

        "slack": """You are drafting a Slack channel announcement. Given context, produce a JSON array of Slack Block Kit blocks.
Include:
- A header with the meeting topic
- A section with the PR summary
- Meeting details (time, attendees)
- A divider and call-to-action

Output ONLY the JSON array of blocks, no extra text.""",

        "dm": """You are drafting a personal Slack DM to notify someone about an upcoming meeting.
Keep it concise, friendly, and first-name friendly.
Include: what the meeting is about (PR context), when it is, and why they're invited.
Output ONLY the message text, no JSON wrapping.""",
    }
    return prompts.get(draft_type, prompts["email"])
