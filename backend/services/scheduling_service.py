"""Scheduling service — slot proposal algorithm."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone


@dataclass
class SlotProposal:
    start: datetime
    end: datetime
    conflicts: list[str]  # emails with conflicts
    score: int  # number of conflicts (lower = better)


def _next_n_business_days(n: int, from_date: date | None = None) -> list[date]:
    """Return the next n weekdays starting from from_date (or today)."""
    start = from_date or date.today()
    days = []
    current = start
    while len(days) < n:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            days.append(current)
    return days


def _divide_into_slots(
    day: date, working_start: time, working_end: time, duration_mins: int, tz_name: str
) -> list[tuple[datetime, datetime]]:
    """Divide a business day into meeting-sized time slots."""
    import zoneinfo

    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    start_dt = datetime.combine(day, working_start, tzinfo=tz)
    end_dt = datetime.combine(day, working_end, tzinfo=tz)
    duration = timedelta(minutes=duration_mins)

    slots = []
    current = start_dt
    while current + duration <= end_dt:
        slots.append((current, current + duration))
        current += duration
    return slots


def _overlaps(
    slot: tuple[datetime, datetime], busy_periods: list[dict]
) -> bool:
    """Check if a slot overlaps with any busy period."""
    slot_start, slot_end = slot
    for busy in busy_periods:
        busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
        busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))
        if slot_start < busy_end and slot_end > busy_start:
            return True
    return False


def propose_slots(
    freebusy: dict[str, list[dict]],
    duration_mins: int = 30,
    working_start: time = time(9, 0),
    working_end: time = time(17, 0),
    timezone_str: str = "UTC",
    horizon_days: int = 5,
) -> list[SlotProposal]:
    """
    Propose the best 3 meeting slots.

    Args:
        freebusy: dict mapping email → list of {start, end} busy periods
        duration_mins: meeting length in minutes
        working_start/end: working hours boundaries
        timezone_str: IANA timezone name
        horizon_days: number of business days to look ahead

    Returns:
        Top 3 SlotProposals sorted by conflict count (ascending), then earliest time.
    """
    candidates: list[SlotProposal] = []
    days = _next_n_business_days(horizon_days)

    for day in days:
        slots = _divide_into_slots(day, working_start, working_end, duration_mins, timezone_str)
        for slot in slots:
            conflicts = [
                email for email, busy_periods in freebusy.items()
                if _overlaps(slot, busy_periods)
            ]
            candidates.append(SlotProposal(
                start=slot[0],
                end=slot[1],
                conflicts=conflicts,
                score=len(conflicts),
            ))

    candidates.sort(key=lambda s: (s.score, s.start))
    return candidates[:3]
