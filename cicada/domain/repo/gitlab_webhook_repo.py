from abc import ABC, abstractmethod
from dataclasses import dataclass
from hashlib import sha3_256
from uuid import UUID

from cicada.domain.user import UserId


@dataclass
class GitlabWebhook:
    id: UUID
    created_by_user_id: UserId
    project_id: int
    hook_id: int
    hashed_secret: str

    def is_valid_secret(self, secret: str) -> bool:
        return sha3_256(secret.encode()).hexdigest() == self.hashed_secret


class IGitlabWebhookRepo(ABC):
    @abstractmethod
    def get_webhook_by_id(self, uuid: UUID) -> GitlabWebhook | None:
        ...

    @abstractmethod
    def add_webhook(self, webhook: GitlabWebhook) -> None:
        ...
