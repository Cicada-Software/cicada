from dataclasses import dataclass

RepositoryId = int


@dataclass
class Repository:
    id: RepositoryId
    url: str
    provider: str
    is_public: bool = False
