"""Google Calendar + Gmail API service — raw httpx calls."""

import base64
from email.mime.text import MIMEText

import httpx
from backend.auth.token_vault import (
    token_vault_client,
    ProviderTokenExpiredError,
    ProviderError,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GoogleService:
    """Low-level Google APIs wrapper. Token fetched per-call from Auth0 Token Vault."""

    CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"
    GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"

    async def _get_headers(self, user_id: str, db=None) -> dict:
        """Get authorization headers — token retrieved from Auth0 Token Vault."""
        logger.info(
            "Fetching Google token from Auth0 Token Vault",
            extra={"data": {"user_id": user_id, "token_source": "auth0_token_vault"}},
        )
        token_data = await token_vault_client.get_user_token(user_id, "google", db=None)
        return {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Content-Type": "application/json",
        }

    def _handle_google_error(self, resp: httpx.Response, user_id: str) -> None:
        """Raise typed provider errors for Google API HTTP failures."""
        if resp.status_code in (401, 403):
            logger.warning(
                "Google authorization failed",
                extra={
                    "data": {
                        "user_id": user_id,
                        "status_code": resp.status_code,
                        "error_type": "ProviderTokenExpiredError",
                        "recoverable": True,
                        "token_source": "auth0_token_vault",
                    }
                },
            )
            raise ProviderTokenExpiredError("google")
        resp.raise_for_status()

    # ── Calendar ──

    async def check_freebusy(
        self, user_id: str, emails: list[str], time_min: str, time_max: str, timezone: str
    ) -> dict:
        """Query Google Calendar free/busy API."""
        logger.info(
            "Calling Google freebusy",
            extra={
                "data": {
                    "user_id": user_id,
                    "emails": emails,
                    "time_min": time_min,
                    "time_max": time_max,
                    "token_source": "auth0_token_vault",
                }
            },
        )
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
        self._handle_google_error(resp, user_id)
        logger.info(
            "Google freebusy call succeeded",
            extra={"data": {"user_id": user_id, "token_source": "auth0_token_vault"}},
        )
        return resp.json()

    async def create_event(self, user_id: str, event_payload: dict) -> str:
        """Create a calendar event. Returns the event ID."""
        logger.info(
            "Creating Google calendar event",
            extra={"data": {"user_id": user_id, "token_source": "auth0_token_vault"}},
        )
        headers = await self._get_headers(user_id)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.CALENDAR_BASE}/calendars/primary/events",
                headers=headers,
                json=event_payload,
                params={"sendUpdates": "all"},
            )
        self._handle_google_error(resp, user_id)
        event_id = resp.json()["id"]
        logger.info(
            "Google calendar event created",
            extra={"data": {"user_id": user_id, "event_id": event_id, "token_source": "auth0_token_vault"}},
        )
        return event_id

    # ── Gmail ──

    async def create_draft(self, user_id: str, to: list[str], subject: str, body: str) -> str:
        """Create a Gmail draft. Returns the draft ID."""
        logger.info(
            "Creating Gmail draft",
            extra={
                "data": {
                    "user_id": user_id,
                    "recipient_count": len(to),
                    "token_source": "auth0_token_vault",
                }
            },
        )
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
        self._handle_google_error(resp, user_id)
        draft_id = resp.json()["id"]
        logger.info(
            "Gmail draft created",
            extra={"data": {"user_id": user_id, "draft_id": draft_id, "token_source": "auth0_token_vault"}},
        )
        return draft_id

    async def send_draft(self, user_id: str, draft_id: str) -> str:
        """Send an existing Gmail draft. Returns the message ID."""
        logger.info(
            "Sending Gmail draft",
            extra={"data": {"user_id": user_id, "draft_id": draft_id, "token_source": "auth0_token_vault"}},
        )
        headers = await self._get_headers(user_id)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.GMAIL_BASE}/users/me/drafts/send",
                headers=headers,
                json={"id": draft_id},
            )
        self._handle_google_error(resp, user_id)
        message_id = resp.json()["id"]
        logger.info(
            "Gmail draft sent",
            extra={"data": {"user_id": user_id, "message_id": message_id, "token_source": "auth0_token_vault"}},
        )
        return message_id


# Singleton
google_service = GoogleService()
