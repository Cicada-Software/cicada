from dataclasses import dataclass
from uuid import UUID

from cicada.api.common.datetime import UtcDatetime
from cicada.api.common.password_hash import PasswordHash

# TODO: use typing.NewType
UserId = UUID


@dataclass
class User:
    id: UserId
    username: str
    password_hash: PasswordHash | None = None
    is_admin: bool = False
    provider: str = "cicada"
    last_login: UtcDatetime | None = None
    email: str | None = None
