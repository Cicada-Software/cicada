from dataclasses import dataclass
from typing import Self
from uuid import UUID

from passlib.context import CryptContext

from cicada.domain.datetime import UtcDatetime

# TODO: use typing.NewType
UserId = UUID


class PasswordHash:
    hash: str

    def __init__(self, hash: str) -> None:
        self.hash = hash

    @classmethod
    def from_password(cls, password: str) -> Self:
        # TODO: add basic password length/strength security checks

        return cls(CryptContext(schemes=["bcrypt"]).hash(password))

    def verify(self, password: str) -> bool:
        ctx = CryptContext(schemes=["bcrypt"])

        return ctx.verify(password, self.hash)

    def __str__(self) -> str:
        return self.hash


@dataclass
class User:
    id: UserId
    username: str
    password_hash: PasswordHash | None = None
    is_admin: bool = False
    provider: str = "cicada"
    last_login: UtcDatetime | None = None
    email: str | None = None
