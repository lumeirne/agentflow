"""Slack API service — raw httpx calls to Slack Web API."""

import httpx
from backend.auth.token_vault import token_vault_client


class SlackService:
    """Low-level Slack Web API wrapper. Token fetched per-call from Token Vault."""

    BASE_URL = "https://slack.com/api"

    async def _get_headers(self, user_id: str) -> dict:
        """Get authorization headers — token is NOT retained after return."""
        token_data = await token_vault_client.get_user_token(user_id, "slack")
        return {"Authorization": f"Bearer {token_data['access_token']}"}

    async def get_channel_members(self, user_id: str, channel_id: str) -> list[dict]:
        """Get members of a Slack channel."""
        headers = await self._get_headers(user_id)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/conversations.members",
                headers=headers,
                params={"channel": channel_id},
            )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")

        # Fetch user info for each member
        member_ids = data.get("members", [])
        members = []
        for mid in member_ids:
            async with httpx.AsyncClient() as client:
                uresp = await client.get(
                    f"{self.BASE_URL}/users.info",
                    headers=await self._get_headers(user_id),  # fresh token each call
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
        return members

    async def post_channel_message(
        self, user_id: str, channel_id: str, blocks: list, text: str = ""
    ) -> str:
        """Post a message to a Slack channel. Returns the message timestamp."""
        headers = await self._get_headers(user_id)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat.postMessage",
                headers=headers,
                json={"channel": channel_id, "blocks": blocks, "text": text},
            )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
        return data["ts"]

    async def send_dm(self, user_id: str, slack_user_id: str, text: str) -> str:
        """Send a direct message to a Slack user. Returns the message timestamp."""
        headers = await self._get_headers(user_id)
        # Open DM conversation
        async with httpx.AsyncClient() as client:
            conv_resp = await client.post(
                f"{self.BASE_URL}/conversations.open",
                headers=headers,
                json={"users": slack_user_id},
            )
        conv_data = conv_resp.json()
        if not conv_data.get("ok"):
            raise RuntimeError(f"Failed to open DM: {conv_data.get('error', 'unknown')}")

        channel_id = conv_data["channel"]["id"]

        # Send message — fetch fresh token
        headers = await self._get_headers(user_id)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat.postMessage",
                headers=headers,
                json={"channel": channel_id, "text": text},
            )
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Failed to send DM: {data.get('error', 'unknown')}")
        return data["ts"]


# Singleton
slack_service = SlackService()
