from datetime import timezone

from cicada.domain.datetime import Datetime, UtcDatetime


def test_parse_utc_datetime_with_z_suffix() -> None:
    date = "2023-02-23 15:31:36.359017Z"

    dt = Datetime.fromisoformat(date)

    assert dt.tzinfo == timezone.utc


def test_normalize_datetime_serialization() -> None:
    expected = "2023-02-23 15:31:36.359017Z"

    tests = (
        "2023-02-23 15:31:36.359017Z",
        "2023-02-23 15:31:36.359017+00:00",
        "2023-02-23T15:31:36.359017Z",
    )

    for test in tests:
        assert str(Datetime.fromisoformat(test)) == expected


def test_utc_datetime_is_always_in_utc_datetime() -> None:
    dt = UtcDatetime.now()

    assert dt.tzinfo == timezone.utc
