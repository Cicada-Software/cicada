from dataclasses import dataclass
from typing import Literal

from cicada.domain.session import Session
from cicada.domain.user import User


@dataclass
class Notification:
    type: Literal["email"]
    user: User
    session: Session


@dataclass
class NotificationEmail:
    send_to: str
    session: Session
    context: str | None
