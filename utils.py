# utils.py

from datetime import datetime, UTC, timedelta


def today_string():
    return datetime.now(UTC).date().isoformat()


def next_midnight_unix():
    now = datetime.now(UTC)

    next_midnight = (
        now + timedelta(days=1)
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    return int(next_midnight.timestamp())