from abc import ABC, abstractmethod

from cicada.domain.cache import CacheObject


class ICacheRepo(ABC):
    @abstractmethod
    def store(self, cache: CacheObject) -> None:
        pass

    @abstractmethod
    def get(
        self,
        repository_url: str,
        key: str,
    ) -> CacheObject | None:
        pass

    @abstractmethod
    def key_exists(
        self,
        repository_url: str,
        key: str,
    ) -> bool:
        pass
