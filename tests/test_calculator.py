from datetime import datetime, timezone

from app.cron.calculator import next_fire_time, next_n_fire_times, compute_missed_fires
from app.cron.parser import CronExpression


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


class TestNextFireTime:
    def test_every_5_minutes(self):
        cron = CronExpression.parse("*/5 * * * *")
        after = _dt("2024-01-01T10:03:00+00:00")
        result = next_fire_time(cron, after, "UTC")
        assert result == _dt("2024-01-01T10:05:00+00:00")

    def test_daily_at_2am(self):
        cron = CronExpression.parse("0 2 * * *")
        after = _dt("2024-01-01T00:00:00+00:00")
        result = next_fire_time(cron, after, "UTC")
        assert result == _dt("2024-01-01T02:00:00+00:00")

    def test_february_29(self):
        cron = CronExpression.parse("0 0 29 2 *")
        after = _dt("2024-03-01T00:00:00+00:00")
        result = next_fire_time(cron, after, "UTC")
        # Next leap year Feb 29 from March 2024 is Feb 2028
        assert result.month == 2
        assert result.day == 29

    def test_dom_and_dow_or_logic(self):
        cron = CronExpression.parse("0 0 1 * Mon")
        after = _dt("2024-01-01T00:00:00+00:00")
        # Jan 1 2024 is a Monday, so it matches DOW too.
        # Next fire should be the next Monday OR the 1st of next month
        result = next_fire_time(cron, after, "UTC")
        # Jan 1 2024 is Monday, next should be Jan 8 (Monday)
        assert result == _dt("2024-01-08T00:00:00+00:00")

    def test_day_31_skips_short_months(self):
        cron = CronExpression.parse("0 0 31 * *")
        after = _dt("2024-04-01T00:00:00+00:00")
        result = next_fire_time(cron, after, "UTC")
        # April has 30 days, next should be May 31
        assert result.month == 5
        assert result.day == 31

    def test_strictly_after(self):
        cron = CronExpression.parse("0 0 * * *")
        after = _dt("2024-01-01T00:00:00+00:00")
        result = next_fire_time(cron, after, "UTC")
        assert result > after

    def test_specific_hour_and_minute(self):
        cron = CronExpression.parse("30 14 * * *")
        after = _dt("2024-01-01T14:30:00+00:00")
        result = next_fire_time(cron, after, "UTC")
        assert result == _dt("2024-01-02T14:30:00+00:00")

    def test_month_boundary(self):
        cron = CronExpression.parse("0 0 1 6 *")
        after = _dt("2024-01-01T00:00:00+00:00")
        result = next_fire_time(cron, after, "UTC")
        assert result.month == 6
        assert result.day == 1

    def test_every_minute_in_hour(self):
        cron = CronExpression.parse("* 3 * * *")
        after = _dt("2024-01-01T03:00:00+00:00")
        result = next_fire_time(cron, after, "UTC")
        assert result == _dt("2024-01-01T03:01:00+00:00")


class TestNextNFireTimes:
    def test_returns_n_times(self):
        cron = CronExpression.parse("0 * * * *")
        after = _dt("2024-01-01T00:00:00+00:00")
        fires = next_n_fire_times(cron, after, "UTC", 5)
        assert len(fires) == 5
        for i in range(1, 5):
            assert fires[i] > fires[i - 1]

    def test_no_duplicates(self):
        cron = CronExpression.parse("*/15 * * * *")
        after = _dt("2024-01-01T00:00:00+00:00")
        fires = next_n_fire_times(cron, after, "UTC", 20)
        assert len(fires) == len(set(fires))


class TestComputeMissedFires:
    def test_with_missed(self):
        cron = CronExpression.parse("0 * * * *")
        last = _dt("2024-01-01T10:00:00+00:00")
        now = _dt("2024-01-01T13:00:00+00:00")
        missed = compute_missed_fires(cron, last, now, "UTC")
        assert len(missed) == 2
        assert missed[0] == _dt("2024-01-01T11:00:00+00:00")
        assert missed[1] == _dt("2024-01-01T12:00:00+00:00")

    def test_no_missed(self):
        cron = CronExpression.parse("0 * * * *")
        last = _dt("2024-01-01T13:00:00+00:00")
        now = _dt("2024-01-01T13:30:00+00:00")
        missed = compute_missed_fires(cron, last, now, "UTC")
        assert len(missed) == 0
