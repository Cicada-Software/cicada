import sqlite3

from cicada.api.infra.db_connection import DbConnection
from cicada.domain.repo.repository_repo import IRepositoryRepo, Permission
from cicada.domain.repository import Repository, RepositoryId
from cicada.domain.user import User, UserId


class RepositoryRepo(IRepositoryRepo, DbConnection):
    def get_repository_by_repo_id(self, id: RepositoryId) -> Repository | None:
        row = self.conn.execute(
            """
            SELECT id, url, provider, is_public
            FROM repositories
            WHERE id=?
            """,
            [id],
        ).fetchone()

        return self._convert(row) if row else None

    def get_repository_by_url_and_provider(self, url: str, provider: str) -> Repository | None:
        row = self.conn.execute(
            """
            SELECT id, url, provider, is_public
            FROM repositories
            WHERE url=? AND provider=?
            """,
            [url, provider],
        ).fetchone()

        return self._convert(row) if row else None

    def update_or_create_repository(
        self, *, url: str, provider: str, is_public: bool
    ) -> Repository:
        repo_id = self.conn.execute(
            """
            INSERT INTO repositories (provider, url, is_public)
            VALUES (?, ?, ?)
            ON CONFLICT DO UPDATE SET url=url, is_public=is_public
            RETURNING id;
            """,
            [provider, url, int(is_public)],
        ).fetchone()[0]

        self.conn.commit()

        return Repository(
            repo_id,
            provider=provider,
            url=url,
            is_public=is_public,
        )

    def can_user_access_repo(
        self,
        user: User,
        repo: Repository,
        *,
        permission: Permission = "owner",
    ) -> bool:
        # TODO: test this

        if user.is_admin:
            return True

        if permission == "read":
            repos = self.conn.execute(
                "SELECT is_public FROM repositories WHERE id=?",
                [repo.id],
            ).fetchone()

            if repos is not None and repos["is_public"]:
                return True

        rows = self.conn.execute(
            """
            SELECT ur.perms
            FROM _user_repos ur
            JOIN repositories r ON r.id = ur.repo_id
            JOIN users u ON u.id = ur.user_id
            WHERE (
                u.username=?
                AND u.platform=?
                AND r.provider=?
                AND r.url=?
                AND ur.perms=?
            );
            """,
            [
                user.username,
                user.provider,
                repo.provider,
                repo.url,
                permission,
            ],
        ).fetchone()

        if not rows or not rows[0]:
            return False

        permission_levels = ["read", "write", "owner"]

        required_level = permission_levels.index(permission)

        return any(permission_levels.index(p) >= required_level for p in rows[0].split(","))

    def update_user_perms_for_repo(
        self, repo: Repository, user_id: UserId, permissions: list[Permission]
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO _user_repos (repo_id, user_id, perms)
            VALUES (
                ?,
                (SELECT id FROM users WHERE uuid=?),
                ?
            )
            ON CONFLICT DO UPDATE SET perms=excluded.perms;
            """,
            [repo.id, user_id, ",".join(permissions)],
        )

        self.conn.commit()

    @staticmethod
    def _convert(row: sqlite3.Row) -> Repository:
        return Repository(
            id=row["id"],
            url=row["url"],
            provider=row["provider"],
            is_public=bool(row["is_public"]),
        )
