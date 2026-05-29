from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .parser import CronExpression
from .timezone_utils import UTC, local_to_utc, utc_to_naive_local

_MAX_ITERATIONS = 5 * 366 * 24 * 60


def next_fire_time(
    cron: CronExpression,
    after_utc: datetime,
    tz_name: str,
) -> datetime:
    """Return the next UTC fire time strictly after after_utc."""
    tz = ZoneInfo(tz_name)
    after_local = utc_to_naive_local(after_utc, tz)

    sorted_months = sorted(cron.months)
    sorted_doms = sorted(cron.days_of_month)
    sorted_hours = sorted(cron.hours)
    sorted_mins = sorted(cron.minutes)

    # Detect fall-back overlap: if after_local is in an ambiguous period
    # AND we've exhausted fold=0 fires in the current hour, we need to
    # search the fold=1 period from the beginning of the hour.
    in_overlap = False
    fold0 = local_to_utc(after_local, tz, fold=0)
    fold1 = local_to_utc(after_local, tz, fold=1)
    if fold0 is not None and fold1 is not None and fold0 != fold1 and fold1 > after_utc:
        # We're in the overlap. Check if there are still fold=0 fires
        # remaining in the current hour.
        remaining_f0_mins = [m for m in sorted_mins if m > after_local.minute]
        if not remaining_f0_mins:
            # No more fold=0 fires — switch to overlap mode
            in_overlap = True

    if in_overlap:
        candidate = after_local.replace(
            minute=sorted_mins[0], second=0, microsecond=0
        )
    else:
        candidate = after_local.replace(second=0, microsecond=0) + timedelta(minutes=1)

    for _ in range(_MAX_ITERATIONS):
        # --- Month ---
        if candidate.month not in cron.months:
            next_m = _next_in_sorted(sorted_months, candidate.month)
            if next_m is None or next_m <= candidate.month:
                candidate = candidate.replace(
                    year=candidate.year + 1,
                    month=sorted_months[0],
                    day=1,
                    hour=0,
                    minute=0,
                )
            else:
                candidate = candidate.replace(month=next_m, day=1, hour=0, minute=0)
            continue

        # --- Day (DOM + DOW with OR logic) ---
        cron_dow = (candidate.weekday() + 1) % 7
        day_match = _day_matches(candidate.day, cron_dow, cron, sorted_doms)
        if not day_match:
            candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
            continue

        # --- Hour ---
        if candidate.hour not in cron.hours:
            next_h = _next_in_sorted(sorted_hours, candidate.hour)
            if next_h is None:
                candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
            else:
                candidate = candidate.replace(hour=next_h, minute=0)
            continue

        # --- Minute ---
        if candidate.minute not in cron.minutes:
            next_min = _next_in_sorted(sorted_mins, candidate.minute)
            if next_min is not None:
                candidate = candidate.replace(minute=next_min)
            else:
                next_h = _next_in_sorted(sorted_hours, candidate.hour)
                if next_h is not None:
                    candidate = candidate.replace(hour=next_h, minute=sorted_mins[0])
                else:
                    candidate = (candidate + timedelta(days=1)).replace(hour=0, minute=0)
            continue

        # --- All fields match — try fold=0 then fold=1 ---
        for fold in (0, 1):
            utc_dt = local_to_utc(candidate, tz, fold=fold)
            if utc_dt is None:
                continue
            if utc_dt > after_utc:
                return utc_dt

        # Neither fold worked — advance
        candidate += timedelta(minutes=1)

    raise RuntimeError("No fire time found within iteration limit")


def next_n_fire_times(
    cron: CronExpression,
    after_utc: datetime,
    tz_name: str,
    n: int,
) -> list[datetime]:
    """Return the next n UTC fire times strictly after after_utc."""
    results: list[datetime] = []
    cursor = after_utc
    for _ in range(n):
        ft = next_fire_time(cron, cursor, tz_name)
        results.append(ft)
        cursor = ft
    return results


def _next_in_sorted(sorted_vals: list[int], current: int) -> int | None:
    """Return the smallest value in sorted_vals strictly greater than current, or None."""
    for v in sorted_vals:
        if v > current:
            return v
    return None


def _day_matches(
    day: int, cron_dow: int, cron: CronExpression, sorted_doms: list[int]
) -> bool:
    if cron.dom_restricted and cron.dow_restricted:
        return day in cron.days_of_month or cron_dow in cron.days_of_week
    elif cron.dom_restricted:
        return day in cron.days_of_month
    elif cron.dow_restricted:
        return cron_dow in cron.days_of_week
    return True


def compute_missed_fires(
    cron: CronExpression,
    last_fire_utc: datetime,
    now_utc: datetime,
    tz_name: str,
    max_fires: int = 1000,
) -> list[datetime]:
    """Compute all fire times between last_fire_utc and now_utc."""
    fires: list[datetime] = []
    cursor = last_fire_utc
    for _ in range(max_fires + 1):
        ft = next_fire_time(cron, cursor, tz_name)
        if ft >= now_utc:
            break
        fires.append(ft)
        cursor = ft
    return fires
