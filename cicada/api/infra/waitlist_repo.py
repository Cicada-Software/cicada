from cicada.api.common.datetime import UtcDatetime
from cicada.api.infra.db_connection import DbConnection
from cicada.api.repo.waitlist_repo import IWaitlistRepo


class WaitlistRepo(IWaitlistRepo, DbConnection):
    def insert_email(self, email: str) -> None:
        super().insert_email(email)

        self.conn.cursor().execute(
            """
            INSERT INTO waitlist ('submitted_at', 'email')
            VALUES (?, ?)
            ON CONFLICT(email) DO NOTHING;
            """,
            [UtcDatetime.now(), email.strip()],
        )

        self.conn.commit()

    def get_emails(self) -> list[tuple[UtcDatetime, str]]:
        rows = (
            self.conn.cursor()
            .execute("SELECT submitted_at, email FROM waitlist;")
            .fetchall()
        )

        return [
            (UtcDatetime.fromisoformat(row["submitted_at"]), row["email"])
            for row in rows
        ]
