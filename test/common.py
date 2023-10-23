from dataclasses import MISSING, Field, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from secrets import token_hex
from types import GenericAlias, NoneType, UnionType
from typing import Any, Literal, NewType, TypeVar
from uuid import UUID, uuid4

from cicada.domain.datetime import Datetime, UtcDatetime
from cicada.domain.triggers import CommitTrigger, GitSha, Trigger


def get_default_type(field_type: Any) -> Any:  # type: ignore
    if (origin := getattr(field_type, "__origin__", None)) and origin == Literal:
        return field_type.__args__[0]

    if isinstance(field_type, UnionType):
        for union_type in field_type.__args__:
            if union_type == NoneType:
                return None

        raise TypeError("Cannot auto build union types")
    if isinstance(field_type, NewType):
        return get_default_type(field_type.__supertype__)

    if isinstance(field_type, GenericAlias):
        return get_default_type(field_type.__origin__)

    if issubclass(field_type, UUID):
        return uuid4()

    if field_type == Datetime:
        return field_type.now(timezone.utc)

    if issubclass(field_type, UtcDatetime | datetime):
        return field_type.now()

    if issubclass(field_type, Enum):
        return next(iter(field_type))

    if issubclass(field_type, Trigger):
        return build(
            CommitTrigger,
            sha=GitSha("deadbeef"),
            ref="refs/heads/master",
            repository_url="https://github.com/user/repo",
            provider="github",
        )

    if issubclass(field_type, GitSha):
        return GitSha(token_hex(4))

    return field_type()


T = TypeVar("T")


# TODO: use better typing for kwargs
def build(ty: type[T], **kwargs: Any) -> T:  # type: ignore
    if not is_dataclass(ty):
        raise TypeError("Type must be a dataclass")

    unset_fields: dict[str, Field] = {}  # type: ignore[type-arg]

    for field in fields(ty):
        if field.default is MISSING and field.default_factory is MISSING:
            unset_fields[field.name] = field

    data = kwargs.copy()

    for missing_key in unset_fields.keys() - kwargs.keys():
        field_type = unset_fields[missing_key].type

        data[missing_key] = get_default_type(field_type)

    return ty(**data)  # type: ignore
