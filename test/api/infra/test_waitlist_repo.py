import pytest

from cicada.api.infra.waitlist_repo import WaitlistRepo
from cicada.domain.datetime import UtcDatetime
from test.api.common import SqliteTestWrapper


class TestWaitlistRepo(SqliteTestWrapper):
    repo: WaitlistRepo

    @classmethod
    def setup_class(cls) -> None:
        cls.reset()

    @classmethod
    def reset(cls) -> None:
        super().reset()

        cls.repo = WaitlistRepo(cls.connection)

    def test_invalid_emails_raise_exception(self) -> None:
        with pytest.raises(ValueError, match="Email cannot be empty"):
            self.repo.insert_email("")

        with pytest.raises(
            ValueError, match='Email must contain a "@" and a "."'
        ):
            self.repo.insert_email("not valid")

        msg = "Email cannot be longer than 256 characters"

        email = list("x" * 257)
        email[1] = "@"
        email[-2] = "."
        email = "".join(email)

        with pytest.raises(ValueError, match=msg):
            self.repo.insert_email(email)

    def test_valid_email_is_entered(self) -> None:
        now = UtcDatetime.now()

        self.repo.insert_email("hello@world.com ")

        emails = self.repo.get_emails()

        assert len(emails) == 1

        submitted_at, email = emails[0]

        assert isinstance(submitted_at, UtcDatetime)
        assert submitted_at >= now
        assert email == "hello@world.com"

        # ensure duplicate email is ignored

        self.repo.insert_email("hello@world.com ")
        assert len(self.repo.get_emails()) == 1
