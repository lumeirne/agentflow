"""Slack tool functions — used by the LangGraph agent executor node.

Typed provider errors are propagated unchanged so the executor can branch on recoverability.
"""

from backend.services.slack_service import slack_service
# Re-export typed errors so callers can import from one place
from backend.auth.token_vault import (  # noqa: F401
    ProviderConnectionMissingError,
    ProviderTokenExpiredError,
    ProviderTokenExchangeError,
    ProviderTemporaryError,
    ProviderError,
)


async def slack_get_channel_members(user_id: str, channel_id: str) -> list[dict]:
    """Get members of a Slack channel."""
    return await slack_service.get_channel_members(user_id, channel_id)


async def slack_post_channel_message(user_id: str, channel_id: str, blocks: list, text: str = "") -> str:
    """Post a message to a Slack channel. Returns the message timestamp."""
    return await slack_service.post_channel_message(user_id, channel_id, blocks, text)


async def slack_send_dm(user_id: str, slack_user_id: str, text: str) -> str:
    """Send a DM to a Slack user. Returns the message timestamp."""
    return await slack_service.send_dm(user_id, slack_user_id, text)
