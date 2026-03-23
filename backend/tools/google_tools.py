"""Google Calendar + Gmail tool functions — used by the LangGraph agent executor node."""

from backend.services.google_service import google_service
from backend.services.scheduling_service import propose_slots, SlotProposal


async def calendar_check_freebusy(
    user_id: str, attendee_emails: list[str],
    time_min: str, time_max: str, timezone: str
) -> dict:
    """Query Google Calendar free/busy for a set of attendees."""
    return await google_service.check_freebusy(user_id, attendee_emails, time_min, time_max, timezone)


async def calendar_propose_slots(
    freebusy_data: dict,
    duration_mins: int = 30,
    working_hours: tuple[str, str] = ("09:00", "17:00"),
    horizon_days: int = 5,
    timezone_str: str = "UTC",
) -> list[SlotProposal]:
    """Compute the best 3 meeting slots from free/busy data."""
    from datetime import time

    start_parts = working_hours[0].split(":")
    end_parts = working_hours[1].split(":")
    working_start = time(int(start_parts[0]), int(start_parts[1]))
    working_end = time(int(end_parts[0]), int(end_parts[1]))

    # Extract busy periods per calendar from Google's freebusy response
    calendars = freebusy_data.get("calendars", {})
    freebusy = {}
    for email, cal_data in calendars.items():
        freebusy[email] = cal_data.get("busy", [])

    return propose_slots(
        freebusy=freebusy,
        duration_mins=duration_mins,
        working_start=working_start,
        working_end=working_end,
        timezone_str=timezone_str,
        horizon_days=horizon_days,
    )


async def calendar_create_event(user_id: str, payload: dict) -> str:
    """Create a Google Calendar event. Returns the event ID."""
    return await google_service.create_event(user_id, payload)


async def gmail_create_draft(user_id: str, to: list[str], subject: str, body: str) -> str:
    """Create a Gmail draft. Returns the draft ID."""
    return await google_service.create_draft(user_id, to, subject, body)


async def gmail_send_message(user_id: str, draft_id: str) -> str:
    """Send a Gmail draft. Returns the message ID."""
    return await google_service.send_draft(user_id, draft_id)
