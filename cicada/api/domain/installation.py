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

    The "provider_id" field is the id the provider (ie, GitHub) has given the
    installation. The "provider_url" is the URL to manage the installation on
    the provider's website.
    """

    id: UUID
    name: str
    provider: Literal["github", "gitlab"]
    scope: InstallationScope
    admin_id: UUID
    provider_id: str | None = None
    provider_url: str | None = None
