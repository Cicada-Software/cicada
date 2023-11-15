from hashlib import sha3_256
from secrets import token_hex
from uuid import uuid4
from cicada.api.infra.gitlab.webhook_repo import GitlabWebhookRepo

from cicada.api.infra.user_repo import UserRepo
from cicada.domain.repo.gitlab_webhook_repo import GitlabWebhook
from cicada.domain.user import User
from test.api.common import SqliteTestWrapper
from test.common import build


class TestGitlabWebhookRepo(SqliteTestWrapper):
    user_repo: UserRepo
    webhook_repo: GitlabWebhookRepo

    @classmethod
    def setup_class(cls) -> None:
        cls.reset()

    @classmethod
    def reset(cls) -> None:
        super().reset()

        cls.user_repo = UserRepo(cls.connection)
        cls.webhook_repo = GitlabWebhookRepo(cls.connection)

    def test_get_webhook_by_id_fails_for_nonexistent_id(self) -> None:
        assert not self.webhook_repo.get_webhook_by_id(uuid4())

    def test_add_and_get_webhook_by_id(self) -> None:
        user = build(User)
        self.user_repo.create_or_update_user(user)

        secret = token_hex(16)
        hashed_secret = sha3_256(secret.encode()).hexdigest()

        webhook = GitlabWebhook(
            id=uuid4(),
            created_by_user_id=user.id,
            project_id=1,
            hook_id=2,
            hashed_secret=hashed_secret,
        )

        # TODO: move verification to its own test
        assert webhook.is_valid_secret(secret)
        assert not webhook.is_valid_secret("asdf")

        self.webhook_repo.add_webhook(webhook)

        got_webhook = self.webhook_repo.get_webhook_by_id(webhook.id)

        assert webhook == got_webhook
