from dataclasses import dataclass
from typing import NewType
from uuid import UUID

from cicada.domain.installation import InstallationId
from cicada.domain.password_hash import PasswordHash

RunnerId = NewType("RunnerId", UUID)


@dataclass
class Runner:
    id: RunnerId
    installation_id: InstallationId
    secret: PasswordHash
    groups: frozenset[str]

    def verify(self, secret: str) -> bool:
        return self.secret.verify(secret)
