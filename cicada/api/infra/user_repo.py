from cicada.api.common.datetime import UtcDatetime
from cicada.api.common.password_hash import PasswordHash
from cicada.api.domain.user import User, UserId
from cicada.api.infra.db_connection import DbConnection
from cicada.api.repo.user_repo import IUserRepo


class UserRepo(IUserRepo, DbConnection):
    # TODO: require username and provider combo
    def get_user_by_username(self, username: str) -> User | None:
        row = self.conn.execute(
            """
            SELECT uuid, username, hash, is_admin, platform, last_login
            FROM users WHERE username=?
            """,
            [username],
        ).fetchone()

        if row:
            return User(
                id=UserId(row["uuid"]),
                username=row["username"],
                password_hash=(
                    PasswordHash(row["hash"]) if row["hash"] else None
                ),
                is_admin=row["is_admin"],
                provider=row["platform"],
                last_login=(
                    UtcDatetime.fromisoformat(row["last_login"])
                    if row["last_login"]
                    else None
                ),
            )

        return None

    def create_or_update_user(self, user: User) -> UserId:
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
            ON CONFLICT DO UPDATE SET
                hash=excluded.hash,
                is_admin=excluded.is_admin
            RETURNING uuid;
            """,
            [
                str(user.id),
                user.username,
                pw_hash,
                user.is_admin,
                user.provider,
            ],
        ).fetchone()[0]

        self.conn.commit()

        return UserId(user_id)

    def update_last_login(self, user: User) -> None:
        self.conn.execute(
            "UPDATE users SET last_login=? WHERE uuid=?",
            [str(UtcDatetime.now()), str(user.id)],
        )

        self.conn.commit()
