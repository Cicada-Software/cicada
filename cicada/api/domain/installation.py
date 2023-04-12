from dataclasses import dataclass
from enum import Enum
from typing import Literal
from uuid import UUID


class InstallationScope(Enum):
    USER = "USER"
    ORGANIZATION = "ORG"

    def __str__(self) -> str:
        return self.value


@dataclass
class Installation:
    """
    An installation is an entity that is created when installing Cicada via a
    provider such as GitHub or Gitlab. This creates an abstraction layer for
    assigning admins, roles, etc.
    """

    id: UUID
    name: str
    provider: Literal["github", "gitlab"]
    scope: InstallationScope
    admin_id: UUID
