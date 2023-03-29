from __future__ import annotations

from datetime import datetime, timezone, tzinfo


class Datetime(datetime):
    @classmethod
    def fromisoformat(cls, date: str) -> Datetime:
        if date.endswith("UTC"):
            dt = cls.strptime(date, "%Y-%m-%d %H:%M:%S %Z")
            dt.__class__ = cls

            return dt.replace(tzinfo=timezone.utc)

        return super().fromisoformat(date.replace("Z", "+00:00"))

    def __str__(self) -> str:
        return super().__str__().replace("+00:00", "Z").replace("T", " ")

    __repr__ = __str__

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> Datetime:
        assert tz

        return super().now(tz)


class UtcDatetime(Datetime):
    @classmethod
    def fromisoformat(cls, date: str) -> UtcDatetime:
        dt = super().fromisoformat(date)
        dt.__class__ = cls

        assert dt.tzinfo == timezone.utc

        return dt  # type: ignore

    @classmethod
    def now(cls, tz: tzinfo | None = timezone.utc) -> UtcDatetime:
        assert tz == timezone.utc

        dt = super().now(tz)
        dt.__class__ = cls

        return dt  # type: ignore
