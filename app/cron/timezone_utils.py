from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


UTC = ZoneInfo("UTC")


def local_to_utc(naive_local: datetime, tz: ZoneInfo, fold: int = 0) -> datetime | None:
    """Convert a naive local datetime to UTC.

    Args:
        fold: 0 for the first occurrence (EDT before fall-back),
              1 for the second occurrence (EST after fall-back).

    Returns None if the local time falls in a DST gap (spring-forward).
    """
    aware = naive_local.replace(tzinfo=tz, fold=fold)
    utc_dt = aware.astimezone(UTC)
    roundtrip = utc_dt.astimezone(tz).replace(tzinfo=None, fold=0)
    if roundtrip != naive_local.replace(fold=0):
        return None
    return utc_dt


def utc_to_naive_local(utc_dt: datetime, tz: ZoneInfo) -> datetime:
    """Convert a UTC datetime to a naive local datetime."""
    return utc_dt.astimezone(tz).replace(tzinfo=None)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
