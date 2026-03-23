"""Google Calendar + Gmail API service — raw httpx calls."""

import base64
from email.mime.text import MIMEText

import httpx
from backend.auth.token_vault import token_vault_client


class GoogleService:
    """Low-level Google APIs wrapper. Token fetched per-call from Token Vault."""

    CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"
    GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"

    async def _get_headers(self, user_id: str) -> dict:
        """Get authorization headers — token is NOT retained after return."""
        token_data = await token_vault_client.get_user_token(user_id, "google")
        return {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Content-Type": "application/json",
        }

    # ── Calendar ──

    async def check_freebusy(
        self, user_id: str, emails: list[str], time_min: str, time_max: str, timezone: str
    ) -> dict:
        """Query Google Calendar free/busy API."""
        headers = await self._get_headers(user_id)
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "timeZone": timezone,
            "items": [{"id": email} for email in emails],
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.CALENDAR_BASE}/freeBusy",
                headers=headers,
                json=body,
            )
        resp.raise_for_status()
        return resp.json()

    async def create_event(self, user_id: str, event_payload: dict) -> str:
        """Create a calendar event. Returns the event ID."""
        headers = await self._get_headers(user_id)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.CALENDAR_BASE}/calendars/primary/events",
                headers=headers,
                json=event_payload,
                params={"sendUpdates": "all"},
            )
        resp.raise_for_status()
        return resp.json()["id"]

    # ── Gmail ──

    async def create_draft(self, user_id: str, to: list[str], subject: str, body: str) -> str:
        """Create a Gmail draft. Returns the draft ID."""
        headers = await self._get_headers(user_id)
        message = MIMEText(body)
        message["to"] = ", ".join(to)
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.GMAIL_BASE}/users/me/drafts",
                headers=headers,
                json={"message": {"raw": raw}},
            )
        resp.raise_for_status()
        return resp.json()["id"]

    async def send_draft(self, user_id: str, draft_id: str) -> str:
        """Send an existing Gmail draft. Returns the message ID."""
        headers = await self._get_headers(user_id)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.GMAIL_BASE}/users/me/drafts/send",
                headers=headers,
                json={"id": draft_id},
            )
        resp.raise_for_status()
        return resp.json()["id"]


# Singleton
google_service = GoogleService()
