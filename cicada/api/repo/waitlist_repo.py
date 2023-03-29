from abc import ABC, abstractmethod

from cicada.api.common.datetime import UtcDatetime


class IWaitlistRepo(ABC):
    @abstractmethod
    def insert_email(self, email: str) -> None:
        if not email:
            raise ValueError("Email cannot be empty")

        if not (set(email) & {"@", "."}):
            raise ValueError('Email must contain a "@" and a "."')

        if len(email.strip()) > 256:
            raise ValueError("Email cannot be longer than 256 characters")

    @abstractmethod
    def get_emails(self) -> list[tuple[UtcDatetime, str]]:
        ...
