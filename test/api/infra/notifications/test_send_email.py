from datetime import timedelta

from cicada.api.infra.notifications.send_email import format_elapsed_time


def test_time_formatting() -> None:
    tests = {
        timedelta(seconds=1): "1 second",
        timedelta(seconds=2): "2 seconds",
        timedelta(minutes=1, seconds=0): "1 minute",
        timedelta(minutes=2, seconds=0): "2 minutes",
        timedelta(minutes=3, seconds=1): "3 minutes, 1 second",
        timedelta(hours=1, minutes=0): "1 hour",
        timedelta(hours=2, minutes=0): "2 hours",
        timedelta(hours=3, minutes=1): "3 hours, 1 minute",
        timedelta(days=1, hours=0): "1 day",
        timedelta(days=2, hours=0): "2 days",
        timedelta(days=3, hours=1): "3 days, 1 hour",
        timedelta(
            days=1, hours=2, minutes=3, seconds=4
        ): "1 day, 2 hours, 3 minutes, 4 seconds",
    }

    for delta, expected in tests.items():
        assert format_elapsed_time(delta) == expected
