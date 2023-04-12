from uuid import UUID

from cicada.api.domain.installation import Installation, InstallationScope
from cicada.api.domain.user import User
from cicada.api.infra.db_connection import DbConnection
from cicada.api.repo.installation_repo import IInstallationRepo


class InstallationRepo(IInstallationRepo, DbConnection):
    def create_installation(self, installation: Installation) -> UUID:
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
                str(installation.id),
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
            [str(installation_id), str(installation.admin_id), "admin"],
        )

        self.conn.commit()

        return UUID(installation_id)

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
            [str(user.id)],
        ).fetchall()

        installations: list[Installation] = []

        for row in rows:
            installations.append(
                Installation(
                    id=UUID(row[0]),
                    name=row[1],
                    provider=row[2],
                    scope=InstallationScope(row[3]),
                    provider_id=row[4],
                    provider_url=row[5],
                    admin_id=UUID(row[6]),
                )
            )

        return installations
