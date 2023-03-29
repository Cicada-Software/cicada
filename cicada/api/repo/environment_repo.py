from abc import ABC, abstractmethod
from dataclasses import dataclass

from cicada.api.domain.repository import RepositoryId


# TODO: move to domain folder
@dataclass
class EnvironmentVariable:
    key: str
    value: str


class IEnvironmentRepo(ABC):
    @abstractmethod
    def get_env_var_for_repo(
        self, id: RepositoryId, key: str
    ) -> EnvironmentVariable | None:
        ...

    @abstractmethod
    def get_env_vars_for_repo(
        self, id: RepositoryId
    ) -> list[EnvironmentVariable]:
        ...

    @abstractmethod
    def set_env_vars_for_repo(
        self, id: RepositoryId, env_vars: list[EnvironmentVariable]
    ) -> None:
        ...
