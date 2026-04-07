# Shared display helpers for Streamlit pages (IST, 12-hour clock, no seconds).
from datetime import timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def to_ist(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def format_ist_datetime(dt, *, include_date=True):
    """e.g. 3-Apr-2026 2:30 PM (no seconds)."""
    if dt is None:
        return "—"
    dt = to_ist(dt)
    h24 = dt.hour
    h12 = h24 % 12 or 12
    ampm = "AM" if h24 < 12 else "PM"
    time_part = f"{h12}:{dt.minute:02d} {ampm}"
    if include_date:
        return f"{dt.day}-{dt.strftime('%b')}-{dt.year} {time_part}"
    return time_part
