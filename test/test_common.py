from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import ClassVar, Literal
from uuid import UUID

import pytest

from cicada.api.common.datetime import UtcDatetime
from test.common import build


def test_builder_basic() -> None:
    @dataclass
    class Person:
        name: str

    assert build(Person, name="bob") == Person("bob")


def test_build_uses_defaults_if_set() -> None:
    @dataclass
    class Person:
        first_name: str = "john"
        last_name: str = field(default_factory=lambda: "smith")
        age: int = field(default=123)

    expected = Person(first_name="john", last_name="smith", age=123)

    assert build(Person) == expected


def test_build_uses_zero_defaults_if_not_set() -> None:
    @dataclass
    class Person:
        name: str
        age: int

    assert build(Person) == Person(name="", age=0)


def test_build_must_be_used_with_dataclass() -> None:
    with pytest.raises(TypeError, match="Type must be a dataclass"):
        build(int)


def test_build_non_deterministic_types() -> None:
    @dataclass
    class Row:
        id: UUID
        created_at: datetime
        updated_at: UtcDatetime

    r1 = build(Row)
    r2 = build(Row)

    assert r1.id != r2.id
    assert r1.created_at != r2.created_at
    assert r1.updated_at != r2.updated_at


def test_build_enum() -> None:
    class Color(Enum):
        RED = "RED"
        GREEN = "GREEN"
        BLUE = "BLUE"

    @dataclass
    class Item:
        color: Color

    assert build(Item) == Item(color=Color.RED)


def test_build_union_none_types() -> None:
    @dataclass
    class Person:
        first_name: str
        last_name: str | None

    assert build(Person) == Person(first_name="", last_name=None)


def test_ignore_classvar_types() -> None:
    @dataclass
    class Person:
        occupation: ClassVar[str]

    class Baker(Person):
        occupation = "baker"

    baker = build(Baker)

    assert baker.occupation == "baker"


def test_build_with_inherited_dataclasses() -> None:
    @dataclass
    class Person:
        name: str

    @dataclass
    class Programmer(Person):
        favorite_lang: str

    assert build(Programmer) == Programmer(name="", favorite_lang="")


def test_override_default_value() -> None:
    @dataclass
    class Person:
        name: str = "bob"

    assert build(Person, name="alice") == Person(name="alice")


def test_build_with_literal() -> None:
    @dataclass
    class Person:
        name: Literal["bob", "alice"]

    assert build(Person) == Person(name="bob")
