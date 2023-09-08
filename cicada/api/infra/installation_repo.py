import sqlite3

from cicada.api.infra.db_connection import DbConnection
from cicada.domain.installation import (
    Installation,
    InstallationId,
    InstallationScope,
)
from cicada.domain.repo.installation_repo import IInstallationRepo
from cicada.domain.repository import Repository, RepositoryId
from cicada.domain.user import User, UserId


class InstallationRepo(IInstallationRepo, DbConnection):
    def create_or_update_installation(
        self, installation: Installation
    ) -> InstallationId:
        installation_id = self.conn.execute(
            """
            INSERT INTO installations (
                uuid, name, provider, scope, provider_id, provider_url
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT DO UPDATE SET name=name
            RETURNING uuid;
            """,
            [
                installation.id,
                installation.name,
                installation.provider,
                str(installation.scope),
                installation.provider_id or "",
                installation.provider_url or "",
            ],
        ).fetchone()[0]

        self.conn.execute(
            """
            INSERT INTO _installation_users (installation_id, user_id, perms)
            VALUES (
                (SELECT id FROM installations WHERE uuid=?),
                (SELECT id FROM users WHERE uuid=?),
                ?
            )
            ON CONFLICT DO NOTHING;
            """,
            [installation_id, installation.admin_id, "admin"],
        )

        self.conn.commit()

        return InstallationId(installation_id)

    def get_installations_for_user(self, user: User) -> list[Installation]:
        rows = self.conn.execute(
            """
            SELECT
                i.uuid,
                i.name,
                i.provider,
                i.scope,
                i.provider_id,
                i.provider_url,
                u.uuid
            FROM installations i
            JOIN _installation_users iu ON iu.installation_id = i.id
            JOIN users u on u.id = iu.user_id
            WHERE u.uuid = ?;
            """,
            [user.id],
        ).fetchall()

        return [self._convert(row) for row in rows]

    def get_installation_by_provider_id(
        self, *, id: str, provider: str
    ) -> Installation | None:
        row = self.conn.execute(
            """
            SELECT
                i.uuid,
                i.name,
                i.provider,
                i.scope,
                i.provider_id,
                i.provider_url,
                u.uuid
            FROM installations i
            JOIN _installation_users iu ON iu.installation_id = i.id
            JOIN users u on u.id = iu.user_id
            WHERE i.provider_id=? AND i.provider=?;
            """,
            [id, provider],
        ).fetchone()

        if not row:
            return None

        return self._convert(row)

    def add_repository_to_installation(
        self, repo: Repository, installation: Installation
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO _installation_repos (installation_id, repo_id)
            VALUES (
                (SELECT id FROM installations WHERE uuid=?),
                ?
            )
            ON CONFLICT DO NOTHING;
            """,
            [installation.id, repo.id],
        )

        self.conn.commit()

    def get_installation_id_by_repository_id(
        self, id: RepositoryId
    ) -> InstallationId | None:
        installation_id = self.conn.execute(
            """
            SELECT i.uuid
            FROM _installation_repos ir
            JOIN installations i ON i.id = ir.installation_id
            WHERE ir.repo_id=?
            """,
            [id],
        ).fetchone()

        return InstallationId(installation_id[0]) if installation_id else None

    def _convert(self, row: sqlite3.Row) -> Installation:
        return Installation(
            id=InstallationId(row[0]),
            name=row[1],
            provider=row[2],
            scope=InstallationScope(row[3]),
            provider_id=row[4],
            provider_url=row[5],
            admin_id=UserId(row[6]),
        )
