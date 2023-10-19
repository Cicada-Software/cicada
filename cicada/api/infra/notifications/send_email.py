import logging
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from cicada.api.settings import DNSSettings, SMTPSettings
from cicada.application.notifications.send_notification import SendNotification
from cicada.domain.notification import Notification, NotificationEmail
from cicada.domain.session import Session
from cicada.domain.user import User

logger = logging.getLogger("cicada")


# TODO: create a generic email notification service
def send_email(email: NotificationEmail) -> None:  # pragma: no cover
    smtp_settings = SMTPSettings()
    cicada_domain = DNSSettings().domain

    msg = EmailMessage()

    assert email.session.finished_at

    elapsed = email.session.finished_at - email.session.started_at

    session_id = email.session.id
    session_run = email.session.run

    msg.set_content(
        f"""\
Workflow failed: {email.context}

Duration: {format_elapsed_time(elapsed)}
Status: {email.session.status.name}

See more info at https://{cicada_domain}/run/{session_id}?run={session_run}\
        """
    )

    msg["Subject"] = "Workflow Failed"
    msg["From"] = f"Cicada <{smtp_settings.username}>"
    msg["To"] = email.send_to

    try:
        # TODO: don't create a new SMTP connection every time
        s = smtplib.SMTP(smtp_settings.domain)
        s.starttls()
        s.login(smtp_settings.username, smtp_settings.password)
        s.send_message(msg)
        s.quit()

    except Exception:
        logger.exception("Could not send email:")


def format_elapsed_time(delta: timedelta) -> str:
    total = delta.total_seconds()

    days, hours = divmod(total, 60 * 60 * 24)
    hours, minutes = divmod(hours, 60 * 60)
    minutes, seconds = divmod(minutes, 60)

    parts: list[str] = []

    def append_unit(unit: str, count: float) -> None:
        if count := int(count):
            if count > 1:
                unit += "s"

            parts.append(f"{count} {unit}")

    append_unit("day", days)
    append_unit("hour", hours)
    append_unit("minute", minutes)
    append_unit("second", seconds)

    return ", ".join(parts)


# TODO: move to its own application service
async def send_failure_notifications(
    user: User | None, sessions: list[Session]
) -> None:
    """
    If any of the sessions failed, send the user a notification.
    """

    if not user:
        return

    for session in sessions:
        if not session.status.is_failure():
            return

        email_cmd = SendNotification(send_email)

        await email_cmd.handle(
            Notification(type="email", user=user, session=session)
        )
