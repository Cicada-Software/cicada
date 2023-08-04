from cicada.api.infra.db_connection import DbConnection
from cicada.domain.datetime import UtcDatetime
from cicada.domain.password_hash import PasswordHash
from cicada.domain.repo.user_repo import IUserRepo
from cicada.domain.user import User, UserId


class UserRepo(IUserRepo, DbConnection):
    # TODO: require username and provider combo
    def get_user_by_username(self, username: str) -> User | None:
        row = self.conn.execute(
            """
            SELECT
                uuid,
                username,
                hash,
                is_admin,
                platform,
                last_login,
                email
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
                email=row["email"],
            )

        return None

    def get_user_by_id(self, id: UserId) -> User | None:
        row = self.conn.execute(
            """
            SELECT
                uuid,
                username,
                hash,
                is_admin,
                platform,
                last_login,
                email
            FROM users WHERE uuid=?
            """,
            [id],
        ).fetchone()

        # TODO: move to helper method
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
                email=row["email"],
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
                platform,
                email
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT DO UPDATE SET
                hash=excluded.hash,
                is_admin=excluded.is_admin
            RETURNING uuid;
            """,
            [
                user.id,
                user.username,
                pw_hash,
                user.is_admin,
                user.provider,
                user.email,
            ],
        ).fetchone()[0]

        self.conn.commit()

        return UserId(user_id)

    def update_last_login(self, user: User) -> None:
        self.conn.execute(
            "UPDATE users SET last_login=? WHERE uuid=?",
            [UtcDatetime.now(), user.id],
        )

        self.conn.commit()
