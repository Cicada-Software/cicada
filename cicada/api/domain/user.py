from dataclasses import dataclass
from uuid import UUID

from cicada.api.common.password_hash import PasswordHash


@dataclass
class User:
    id: UUID
    username: str
    password_hash: PasswordHash | None = None
    is_admin: bool = False
    provider: str = "cicada"
