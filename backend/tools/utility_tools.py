"""Utility tools — identity resolution, title generation, content drafting."""

from backend.services.llm_service import llm_service


async def resolve_team_members(github_usernames: list[str], user_id: str, db) -> dict:
    """
    Resolve GitHub usernames to email + Slack identities.

    Returns: {
        "resolved": [{"github": "...", "email": "...", "slack_id": "..."}],
        "unresolved": ["username1", ...]
    }
    """
    from backend.services.identity_service import IdentityService

    identity_service = IdentityService(db)
    resolved = []
    unresolved = []

    for username in github_usernames:
        email = await identity_service.resolve_github_to_email(user_id, username)
        slack_id = await identity_service.resolve_github_to_slack(user_id, username)

        if email or slack_id:
            resolved.append({
                "github": username,
                "email": email,
                "slack_id": slack_id,
            })
        else:
            unresolved.append(username)

    return {"resolved": resolved, "unresolved": unresolved}


async def generate_meeting_title(pr_summary: str) -> str:
    """Generate a meeting title from a PR summary using the LLM."""
    return await llm_service.summarize_pr({"summary_for_title": pr_summary})


async def generate_email_draft(context: dict) -> dict:
    """Generate an email draft using the LLM."""
    return await llm_service.draft_email(context)


async def generate_slack_message(context: dict) -> list:
    """Generate Slack Block Kit blocks using the LLM."""
    return await llm_service.draft_slack(context)


async def generate_dm_message(context: dict, recipient: str) -> str:
    """Generate a personal DM message using the LLM."""
    return await llm_service.draft_dm(context, recipient)
