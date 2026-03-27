"""Slack API service — raw httpx calls to Slack Web API."""

import httpx
from backend.auth.token_vault import (
    token_vault_client,
    ProviderTokenExpiredError,
    ProviderError,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Auth0 connection name for Slack may differ from the logical key.
# The token_vault_client handles the mapping via settings.AUTH0_SLACK_CONNECTION.
_SLACK_PROVIDER_KEY = "slack"


class SlackService:
    """Low-level Slack Web API wrapper. Token fetched per-call from Auth0 Token Vault."""

    BASE_URL = "https://slack.com/api"

    async def _get_token(self, user_id: str) -> str:
        """Retrieve Slack access token from Auth0 Token Vault."""
        logger.info(
            "Fetching Slack token from Auth0 Token Vault",
            extra={"data": {"user_id": user_id, "token_source": "auth0_token_vault"}},
        )
        token_data = await token_vault_client.get_user_token(user_id, _SLACK_PROVIDER_KEY, db=None)
        return token_data["access_token"]

    def _check_slack_response(self, data: dict, user_id: str, operation: str) -> None:
        """Raise typed errors for Slack API-level failures."""
        if not data.get("ok"):
            error = data.get("error", "unknown")
            if error in ("token_revoked", "invalid_auth", "not_authed"):
                logger.warning(
                    "Slack token revoked or invalid",
                    extra={
                        "data": {
                            "user_id": user_id,
                            "operation": operation,
                            "error": error,
                            "error_type": "ProviderTokenExpiredError",
                            "recoverable": True,
                            "token_source": "auth0_token_vault",
                        }
                    },
                )
                raise ProviderTokenExpiredError(_SLACK_PROVIDER_KEY)
            logger.warning(
                "Slack API returned error",
                extra={
                    "data": {
                        "user_id": user_id,
                        "operation": operation,
                        "error": error,
                        "token_source": "auth0_token_vault",
                    }
                },
            )
            raise RuntimeError(f"Slack API error ({operation}): {error}")

    async def get_channel_members(self, user_id: str, channel_id: str) -> list[dict]:
        """Get members of a Slack channel."""
        logger.info(
            "Fetching Slack channel members",
            extra={"data": {"user_id": user_id, "channel_id": channel_id, "token_source": "auth0_token_vault"}},
        )
        token = await self._get_token(user_id)
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/conversations.members",
                headers=headers,
                params={"channel": channel_id},
            )
        resp.raise_for_status()
        data = resp.json()
        self._check_slack_response(data, user_id, "conversations.members")

        member_ids = data.get("members", [])
        members = []
        for mid in member_ids:
            # Re-fetch token per call to avoid stale token mid-loop
            fresh_token = await self._get_token(user_id)
            async with httpx.AsyncClient() as client:
                uresp = await client.get(
                    f"{self.BASE_URL}/users.info",
                    headers={"Authorization": f"Bearer {fresh_token}"},
                    params={"user": mid},
                )
            udata = uresp.json()
            if udata.get("ok"):
                user_info = udata["user"]
                members.append({
                    "id": mid,
                    "name": user_info.get("name", ""),
                    "real_name": user_info.get("real_name", ""),
                    "display_name": user_info.get("profile", {}).get("display_name", ""),
                })
        logger.info(
            "Fetched Slack channel members",
            extra={
                "data": {
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "count": len(members),
                    "token_source": "auth0_token_vault",
                }
            },
        )
        return members

    async def post_channel_message(
        self, user_id: str, channel_id: str, blocks: list, text: str = ""
    ) -> str:
        """Post a message to a Slack channel. Returns the message timestamp."""
        logger.info(
            "Posting Slack channel message",
            extra={"data": {"user_id": user_id, "channel_id": channel_id, "token_source": "auth0_token_vault"}},
        )
        token = await self._get_token(user_id)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat.postMessage",
                headers={"Authorization": f"Bearer {token}"},
                json={"channel": channel_id, "blocks": blocks, "text": text},
            )
        resp.raise_for_status()
        data = resp.json()
        self._check_slack_response(data, user_id, "chat.postMessage")
        logger.info(
            "Slack channel message posted",
            extra={
                "data": {
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "ts": data["ts"],
                    "token_source": "auth0_token_vault",
                }
            },
        )
        return data["ts"]

    async def send_dm(self, user_id: str, slack_user_id: str, text: str) -> str:
        """Send a direct message to a Slack user. Returns the message timestamp."""
        logger.info(
            "Sending Slack DM",
            extra={"data": {"user_id": user_id, "slack_user_id": slack_user_id, "token_source": "auth0_token_vault"}},
        )
        token = await self._get_token(user_id)
        async with httpx.AsyncClient() as client:
            conv_resp = await client.post(
                f"{self.BASE_URL}/conversations.open",
                headers={"Authorization": f"Bearer {token}"},
                json={"users": slack_user_id},
            )
        conv_data = conv_resp.json()
        self._check_slack_response(conv_data, user_id, "conversations.open")
        channel_id = conv_data["channel"]["id"]

        fresh_token = await self._get_token(user_id)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat.postMessage",
                headers={"Authorization": f"Bearer {fresh_token}"},
                json={"channel": channel_id, "text": text},
            )
        data = resp.json()
        self._check_slack_response(data, user_id, "chat.postMessage (DM)")
        logger.info(
            "Slack DM sent",
            extra={
                "data": {
                    "user_id": user_id,
                    "slack_user_id": slack_user_id,
                    "ts": data["ts"],
                    "token_source": "auth0_token_vault",
                }
            },
        )
        return data["ts"]


# Singleton
slack_service = SlackService()
