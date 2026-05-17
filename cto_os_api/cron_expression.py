"""Phase 14 — minimal cron expression parser + next-fire calculator.

Subset: ``minute hour day month weekday``. Each field supports ``*``,
single integer, range ``a-b``, list ``a,b,c``, step ``*/n`` or ``a-b/n``.
``weekday`` uses 0-6 (Sun=0). Calls fall back to the cadence enum when an
expression is missing or invalid.

We do not import ``croniter``. The next-fire calculator scans forward
minute-by-minute, capped at 366 days to avoid runaway loops on
expressions that never match (e.g. ``31 * * 2 *`` doesn't exist).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable


FIELD_BOUNDS = [
    (0, 59),   # minute
    (0, 23),   # hour
    (1, 31),   # day of month
    (1, 12),   # month
    (0, 6),    # day of week (Sun=0)
]
FIELD_NAMES = ("minute", "hour", "day", "month", "weekday")


_FIELD_RE = re.compile(r"^[\d,*/-]+$")
MAX_SCAN_MINUTES = 366 * 24 * 60


class CronExpressionError(ValueError):
    """Raised when a cron expression is malformed."""


def _parse_field(spec: str, low: int, high: int) -> set[int]:
    if not spec or not _FIELD_RE.match(spec):
        raise CronExpressionError(f"invalid field {spec!r}")
    values: set[int] = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            base, step_str = part.split("/", 1)
            if not step_str.isdigit() or int(step_str) <= 0:
                raise CronExpressionError(f"invalid step in {part!r}")
            step = int(step_str)
        else:
            base = part
        if base == "*" or base == "":
            start, end = low, high
        elif "-" in base:
            try:
                a, b = base.split("-", 1)
                start, end = int(a), int(b)
            except ValueError as exc:
                raise CronExpressionError(f"invalid range in {part!r}") from exc
        else:
            if not base.lstrip("-").isdigit():
                raise CronExpressionError(f"invalid token {part!r}")
            start = end = int(base)
        if start < low or end > high or start > end:
            raise CronExpressionError(
                f"value out of bounds in {part!r} for [{low},{high}]"
            )
        values.update(range(start, end + 1, step))
    return values


def parse(expression: str) -> tuple[set[int], ...]:
    parts = expression.strip().split()
    if len(parts) != 5:
        raise CronExpressionError(
            f"expected 5 fields (minute hour day month weekday), got {len(parts)}"
        )
    return tuple(_parse_field(part, lo, hi) for part, (lo, hi) in zip(parts, FIELD_BOUNDS))


def matches(expression: str, when: datetime) -> bool:
    minutes, hours, days, months, weekdays = parse(expression)
    # Python: Monday=0 ... Sunday=6. Cron: Sunday=0 ... Saturday=6.
    cron_weekday = (when.weekday() + 1) % 7
    return (
        when.minute in minutes
        and when.hour in hours
        and when.day in days
        and when.month in months
        and cron_weekday in weekdays
    )


def next_fire(expression: str, after: datetime | None = None) -> datetime | None:
    minutes, hours, days, months, weekdays = parse(expression)
    start = (after or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    candidate = start + timedelta(minutes=1)
    for _ in range(MAX_SCAN_MINUTES):
        cron_weekday = (candidate.weekday() + 1) % 7
        if (
            candidate.minute in minutes
            and candidate.hour in hours
            and candidate.day in days
            and candidate.month in months
            and cron_weekday in weekdays
        ):
            return candidate
        candidate += timedelta(minutes=1)
    return None
