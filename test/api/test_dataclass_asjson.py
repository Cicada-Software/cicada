from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import ClassVar

from cicada.common.json import asjson


def test_stringify_basic_dataclass() -> None:
    @dataclass
    class Person:
        name: str
        age: int

    assert asjson(Person("bob", 123)) == {"name": "bob", "age": 123}


def test_stringify_datetimes() -> None:
    @dataclass
    class Event:
        at: datetime

    now = datetime.now(timezone.utc)

    assert asjson(Event(now)) == {"at": str(now)}


def test_stringify_nested() -> None:
    @dataclass
    class Event:
        at: datetime

    @dataclass
    class TodoItem:
        event: Event

    now = datetime.now(timezone.utc)

    assert asjson(TodoItem(Event(now))) == {"event": {"at": str(now)}}


def test_stringify_list() -> None:
    @dataclass
    class Event:
        at: datetime

    @dataclass
    class Events:
        events: list[Event]

    now = datetime.now(timezone.utc)

    assert asjson(Events([Event(now)])) == {"events": [{"at": str(now)}]}


def test_stringified_none_field_are_included() -> None:
    @dataclass
    class Event:
        at: datetime | None = None

    assert asjson(Event()) == {"at": None}


def test_stringify_class_var_fields_of_class() -> None:
    @dataclass
    class Event:
        a: ClassVar[str] = "a default"
        b = "b default"
        c: str = "c default"

        def f(self) -> None:
            """This shouldn't be stringified"""

    got = asjson(Event(c="different"))
    expected = {"a": "a default", "b": "b default", "c": "different"}

    assert got == expected


def test_stringify_enum() -> None:
    class ItemKind(Enum):
        SMALL = "S"
        MEDIUM = "M"
        LARGE = "L"

    @dataclass
    class Item:
        kind: ItemKind

    got = asjson(Item(ItemKind.SMALL))
    expected = {"kind": "S"}

    assert got == expected
