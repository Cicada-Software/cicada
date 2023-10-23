import asyncio
from collections.abc import Callable

from cicada.domain.notification import Notification, NotificationEmail
from cicada.domain.triggers import CommitTrigger, IssueTrigger, Trigger

EmailSender = Callable[[NotificationEmail], None]


class SendNotification:  # pragma: no cover
    """
    Send a notification when a workflow fails. Eventually this service will be
    able to support multiple notification types, but for now it only supports
    email.
    """

    def __init__(self, send_email: EmailSender) -> None:
        self.send_email = send_email

    async def handle(self, notification: Notification) -> None:
        assert notification.type == "email"

        if not notification.user.email:
            return

        email = NotificationEmail(
            send_to=notification.user.email,
            session=notification.session,
            context=self.get_context_from_trigger(notification.session.trigger),
        )

        await asyncio.to_thread(lambda: self.send_email(email))

    def get_context_from_trigger(self, trigger: Trigger) -> str | None:
        if isinstance(trigger, CommitTrigger):
            return trigger.message.splitlines()[0].strip()

        if isinstance(trigger, IssueTrigger):
            return trigger.title.strip()

        return None
