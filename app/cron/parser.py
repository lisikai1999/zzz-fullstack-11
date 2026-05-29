from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CronExpression:
    minutes: frozenset[int]
    hours: frozenset[int]
    days_of_month: frozenset[int]
    months: frozenset[int]
    days_of_week: frozenset[int]

    @property
    def dom_restricted(self) -> bool:
        return self.days_of_month != frozenset(range(1, 32))

    @property
    def dow_restricted(self) -> bool:
        return self.days_of_week != frozenset(range(7))

    @classmethod
    def parse(cls, expr: str) -> CronExpression:
        parts = expr.split()
        if len(parts) != 5:
            raise ValueError(f"Expected 5 fields, got {len(parts)}: {expr!r}")

        minutes = _parse_field(parts[0], 0, 59)
        hours = _parse_field(parts[1], 0, 23)
        doms = _parse_field(parts[2], 1, 31)
        months = _parse_field(parts[3], 1, 12)
        dows = _parse_dow_field(parts[4])

        return cls(
            minutes=frozenset(minutes),
            hours=frozenset(hours),
            days_of_month=frozenset(doms),
            months=frozenset(months),
            days_of_week=frozenset(dows),
        )


def _parse_field(field_str: str, min_val: int, max_val: int) -> set[int]:
    result: set[int] = set()
    for part in field_str.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"Empty segment in field {field_str!r}")
        if "/" in part:
            range_part, step_str = part.split("/", 1)
            step = int(step_str)
            if step <= 0:
                raise ValueError(f"Step must be positive, got {step}")
            if range_part == "*":
                start, end = min_val, max_val
            elif "-" in range_part:
                start, end = map(int, range_part.split("-", 1))
            else:
                start = int(range_part)
                end = max_val
            _validate_range(start, end, min_val, max_val)
            result.update(range(start, end + 1, step))
        elif "-" in part:
            start, end = map(int, part.split("-", 1))
            _validate_range(start, end, min_val, max_val)
            result.update(range(start, end + 1))
        elif part == "*":
            result.update(range(min_val, max_val + 1))
        else:
            val = int(part)
            _validate_value(val, min_val, max_val)
            result.add(val)

    return result


_DOW_NAMES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6,
}


def _parse_dow_field(field_str: str) -> set[int]:
    resolved = field_str.upper()
    for name, num in _DOW_NAMES.items():
        resolved = resolved.replace(name, str(num))
    raw = _parse_field(resolved, 0, 7)
    if 7 in raw:
        raw.discard(7)
        raw.add(0)
    return raw


def _validate_range(start: int, end: int, min_val: int, max_val: int) -> None:
    if start > end:
        raise ValueError(f"Range start {start} > end {end}")
    _validate_value(start, min_val, max_val)
    _validate_value(end, min_val, max_val)


def _validate_value(val: int, min_val: int, max_val: int) -> None:
    if val < min_val or val > max_val:
        raise ValueError(f"Value {val} out of range [{min_val}, {max_val}]")
