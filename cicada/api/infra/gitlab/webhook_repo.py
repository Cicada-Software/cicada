from uuid import UUID

from cicada.api.infra.db_connection import DbConnection
from cicada.domain.repo.gitlab_webhook_repo import GitlabWebhook, IGitlabWebhookRepo
from cicada.domain.user import UserId


class GitlabWebhookRepo(IGitlabWebhookRepo, DbConnection):
    def get_webhook_by_id(self, uuid: UUID) -> GitlabWebhook | None:
        row = self.conn.execute(
            """
            SELECT
                uuid,
                (SELECT uuid FROM users WHERE id=created_by_user_id) AS created_by_user_id,
                project_id,
                hook_id,
                hashed_secret
            FROM gitlab_repo_webhooks
            WHERE uuid=?;
            """,
            [uuid],
        ).fetchone()

        if not row:
            return None

        return GitlabWebhook(
            id=UUID(row["uuid"]),
            created_by_user_id=UserId(row["created_by_user_id"]),
            project_id=int(row["project_id"]),
            hook_id=int(row["hook_id"]),
            hashed_secret=row["hashed_secret"],
        )

    def add_webhook(self, webhook: GitlabWebhook) -> None:
        self.conn.execute(
            """
            INSERT INTO gitlab_repo_webhooks (
                uuid,
                created_by_user_id,
                project_id,
                hook_id,
                hashed_secret
            ) VALUES (
                ?,
                (SELECT id FROM users WHERE uuid=?),
                ?,
                ?,
                ?
            );
            """,
            [
                webhook.id,
                webhook.created_by_user_id,
                webhook.project_id,
                webhook.hook_id,
                webhook.hashed_secret,
            ],
        )

        self.conn.commit()
