import pytest

from app.cron.parser import CronExpression, _parse_field


class TestParseField:
    def test_wildcard(self):
        assert _parse_field("*", 0, 59) == set(range(60))

    def test_single_value(self):
        assert _parse_field("5", 0, 59) == {5}

    def test_list(self):
        assert _parse_field("1,15,30", 0, 59) == {1, 15, 30}

    def test_range(self):
        assert _parse_field("1-5", 0, 59) == {1, 2, 3, 4, 5}

    def test_step(self):
        assert _parse_field("*/15", 0, 59) == {0, 15, 30, 45}

    def test_range_step(self):
        assert _parse_field("1-15/3", 0, 59) == {1, 4, 7, 10, 13}

    def test_combined(self):
        result = _parse_field("0,15,30-45/5", 0, 59)
        assert result == {0, 15, 30, 35, 40, 45}

    def test_step_from_single(self):
        result = _parse_field("5/10", 0, 59)
        assert result == {5, 15, 25, 35, 45, 55}

    def test_invalid_out_of_range(self):
        with pytest.raises(ValueError):
            _parse_field("60", 0, 59)

    def test_invalid_negative_step(self):
        with pytest.raises(ValueError):
            _parse_field("*/0", 0, 59)

    def test_invalid_range_start_gt_end(self):
        with pytest.raises(ValueError):
            _parse_field("5-1", 0, 59)


class TestCronExpression:
    def test_parse_wildcard(self):
        cron = CronExpression.parse("* * * * *")
        assert cron.minutes == frozenset(range(60))
        assert cron.hours == frozenset(range(24))
        assert cron.days_of_month == frozenset(range(1, 32))
        assert cron.months == frozenset(range(1, 13))
        assert cron.days_of_week == frozenset(range(7))

    def test_parse_every_5_minutes(self):
        cron = CronExpression.parse("*/5 * * * *")
        assert cron.minutes == frozenset({0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55})

    def test_parse_complex(self):
        cron = CronExpression.parse("0 2 1 * Mon")
        assert cron.minutes == frozenset({0})
        assert cron.hours == frozenset({2})
        assert cron.days_of_month == frozenset({1})
        assert cron.days_of_week == frozenset({1})  # Monday

    def test_dow_7_alias(self):
        cron = CronExpression.parse("* * * * 7")
        assert cron.days_of_week == frozenset({0})  # 7 → 0 (Sunday)

    def test_dom_restricted(self):
        cron = CronExpression.parse("0 0 1 * *")
        assert cron.dom_restricted is True
        assert cron.dow_restricted is False

    def test_dow_restricted(self):
        cron = CronExpression.parse("0 0 * * Mon")
        assert cron.dom_restricted is False
        assert cron.dow_restricted is True

    def test_both_restricted(self):
        cron = CronExpression.parse("0 0 1 * Mon")
        assert cron.dom_restricted is True
        assert cron.dow_restricted is True

    def test_neither_restricted(self):
        cron = CronExpression.parse("0 0 * * *")
        assert cron.dom_restricted is False
        assert cron.dow_restricted is False

    def test_invalid_field_count(self):
        with pytest.raises(ValueError, match="5 fields"):
            CronExpression.parse("* * *")

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            CronExpression.parse("60 * * * *")

    def test_invalid_month(self):
        with pytest.raises(ValueError):
            CronExpression.parse("* * * 13 *")
