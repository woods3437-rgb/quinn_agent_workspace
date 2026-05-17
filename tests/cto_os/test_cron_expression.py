"""Phase 14 — cron expression parser + next-fire."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cto_os_api.cron_expression import CronExpressionError, matches, next_fire, parse


def test_parses_simple_expressions():
    parse("0 9 * * 1-5")
    parse("0 8 * * *")
    parse("*/15 * * * *")


def test_rejects_bad_field_count():
    with pytest.raises(CronExpressionError):
        parse("0 9 * *")


def test_rejects_out_of_bounds():
    with pytest.raises(CronExpressionError):
        parse("0 25 * * *")
    with pytest.raises(CronExpressionError):
        parse("0 9 * * 9")


def test_next_fire_daily_at_8am():
    # Sunday 2026-05-17 03:00 UTC → next 08:00 UTC same day.
    start = datetime(2026, 5, 17, 3, 0, tzinfo=timezone.utc)
    nxt = next_fire("0 8 * * *", after=start)
    assert nxt == datetime(2026, 5, 17, 8, 0, tzinfo=timezone.utc)


def test_next_fire_weekdays_9am():
    # 2026-05-16 is a Saturday; next 09:00 UTC weekday is Monday 2026-05-18.
    saturday = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    nxt = next_fire("0 9 * * 1-5", after=saturday)
    assert nxt.weekday() == 0  # Monday
    assert nxt.hour == 9 and nxt.minute == 0


def test_matches_uses_cron_weekday():
    # Sunday in cron == 0; Python weekday 6.
    sunday = datetime(2026, 5, 17, 9, 0, tzinfo=timezone.utc)
    assert matches("0 9 * * 0", sunday) is True
    assert matches("0 9 * * 1-5", sunday) is False
