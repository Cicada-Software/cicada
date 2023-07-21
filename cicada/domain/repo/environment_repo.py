from abc import ABC, abstractmethod

from cicada.domain.env_var import EnvironmentVariable
from cicada.domain.repository import RepositoryId


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
