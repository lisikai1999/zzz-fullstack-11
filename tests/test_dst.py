from datetime import datetime, timedelta, timezone

from app.cron.calculator import next_fire_time, next_n_fire_times
from app.cron.parser import CronExpression
from app.cron.timezone_utils import local_to_utc, utc_to_naive_local

from zoneinfo import ZoneInfo


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


NY = ZoneInfo("America/New_York")


class TestTimezoneUtils:
    def test_normal_conversion(self):
        utc_dt = _dt("2024-03-10T10:00:00+00:00")
        naive_local = utc_to_naive_local(utc_dt, NY)
        # Mar 10 is spring-forward day; by 10:00 UTC, EDT is in effect (UTC-4)
        assert naive_local.hour == 6

    def test_spring_forward_gap(self):
        # 2:30 AM on March 10 2024 in America/New_York doesn't exist
        from datetime import datetime as dt
        naive = dt(2024, 3, 10, 2, 30)
        result = local_to_utc(naive, NY)
        assert result is None  # gap detected

    def test_fall_back_first_occurrence(self):
        # 1:30 AM on Nov 3 2024 occurs twice — fold=0 gives EDT (UTC-4)
        from datetime import datetime as dt
        naive = dt(2024, 11, 3, 1, 30)
        result = local_to_utc(naive, NY)
        assert result is not None
        # First occurrence: 1:30 AM EDT = 05:30 UTC
        assert result.hour == 5

    def test_normal_time_not_in_gap(self):
        from datetime import datetime as dt
        naive = dt(2024, 3, 10, 3, 30)
        result = local_to_utc(naive, NY)
        assert result is not None


class TestDSTSpringForward:
    def test_230am_does_not_fire_on_spring_forward(self):
        """Cron '30 2 * * *' should NOT fire on the spring-forward day
        because 2:30 AM doesn't exist."""
        cron = CronExpression.parse("30 2 * * *")
        # Search from just after midnight on March 10 2024 (spring forward day)
        after = _dt("2024-03-10T06:01:00+00:00")  # 1:01 AM EST
        result = next_fire_time(cron, after, "America/New_York")
        # Should NOT be March 10 2:30 AM (it doesn't exist)
        # Should be March 11 2:30 AM
        assert result.day != 10 or result.month != 3
        # More precisely, the next fire should be on March 11
        local = result.astimezone(NY).replace(tzinfo=None)
        assert local.day == 11

    def test_3am_fires_normally_on_spring_forward_day(self):
        """Cron '0 3 * * *' should fire on the spring-forward day at 3 AM."""
        cron = CronExpression.parse("0 3 * * *")
        after = _dt("2024-03-10T06:01:00+00:00")  # 1:01 AM EST
        result = next_fire_time(cron, after, "America/New_York")
        local = result.astimezone(NY).replace(tzinfo=None)
        assert local.day == 10
        assert local.hour == 3


class TestDSTFallBack:
    def test_130am_fires_twice_on_fall_back(self):
        """Cron '30 1 * * *' should fire twice on fall-back day:
        once at 1:30 AM EDT and once at 1:30 AM EST."""
        cron = CronExpression.parse("30 1 * * *")
        # Start from before the fall-back transition
        after = _dt("2024-11-03T04:00:00+00:00")  # midnight EDT
        fires = next_n_fire_times(cron, after, "America/New_York", 3)

        # First fire: 1:30 AM EDT = 05:30 UTC on Nov 3
        local_first = fires[0].astimezone(NY).replace(tzinfo=None)
        assert local_first.day == 3
        assert local_first.hour == 1
        assert local_first.minute == 30
        assert fires[0] == _dt("2024-11-03T05:30:00+00:00")

        # Second fire: 1:30 AM EST = 06:30 UTC on Nov 3 (fall-back)
        local_second = fires[1].astimezone(NY).replace(tzinfo=None)
        assert local_second.day == 3
        assert fires[1] == _dt("2024-11-03T06:30:00+00:00")

        # Third fire should be on Nov 4
        local_third = fires[2].astimezone(NY).replace(tzinfo=None)
        assert local_third.day == 4

    def test_every_minute_in_1am_hour_during_fall_back(self):
        """'* 1 * * *' during fall-back should fire for all 120 minutes
        (60 EDT + 60 EST)."""
        cron = CronExpression.parse("* 1 * * *")
        # Start from 1 second before 1:00 AM EDT so we capture all 120 fires
        after = _dt("2024-11-03T04:59:59+00:00")
        fires = next_n_fire_times(cron, after, "America/New_York", 130)

        # All fires on Nov 3 in local time should have hour=1
        nov3_fires = [
            f for f in fires
            if f.astimezone(NY).replace(tzinfo=None).day == 3
            and f.astimezone(NY).replace(tzinfo=None).month == 11
        ]
        # Should be 120 fires (60 minutes at EDT + 60 minutes at EST)
        assert len(nov3_fires) == 120


class TestBerlinTimezone:
    def test_berlin_spring_forward(self):
        """Berlin springs forward on 2024-03-31 at 2:00 AM → 3:00 AM."""
        cron = CronExpression.parse("30 2 * * *")
        after = _dt("2024-03-31T00:00:00+00:00")  # 1:00 AM CET
        result = next_fire_time(cron, after, "Europe/Berlin")
        berlin = ZoneInfo("Europe/Berlin")
        local = result.astimezone(berlin).replace(tzinfo=None)
        # 2:30 AM doesn't exist on March 31 in Berlin, should skip to next day
        assert local.day != 31 or local.month != 3
