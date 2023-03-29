from uuid import UUID

from cicada.api.common.password_hash import PasswordHash
from cicada.api.domain.repository import RepositoryId
from cicada.api.domain.user import User
from cicada.api.infra.db_connection import DbConnection
from cicada.api.repo.user_repo import IUserRepo


class UserRepo(IUserRepo, DbConnection):
    # TODO: require username and provider combo
    def get_user_by_username(self, username: str) -> User | None:
        row = self.conn.execute(
            """
            SELECT uuid, username, hash, is_admin, platform
            FROM users WHERE username=?
            """,
            [username],
        ).fetchone()

        if row:
            return User(
                id=UUID(row[0]),
                username=row[1],
                password_hash=PasswordHash(row[2]) if row[2] else None,
                is_admin=row[3],
                provider=row[4],
            )

        return None

    def create_or_update_user(self, user: User) -> UUID:
        pw_hash = str(user.password_hash) if user.password_hash else ""

        user_id = self.conn.execute(
            """
            INSERT INTO users (
                uuid,
                username,
                hash,
                is_admin,
                platform
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT DO UPDATE SET hash=?, is_admin=?
            RETURNING uuid;
            """,
            [
                str(user.id),
                user.username,
                pw_hash,
                user.is_admin,
                user.provider,
                pw_hash,
                user.is_admin,
            ],
        ).fetchone()[0]

        self.conn.commit()

        return UUID(user_id)

    def can_user_see_repo(self, user_id: UUID, repo_id: RepositoryId) -> bool:
        return False
