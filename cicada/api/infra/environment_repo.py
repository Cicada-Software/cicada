from cicada.api.infra.db_connection import DbConnection
from cicada.domain.env_var import EnvironmentVariable
from cicada.domain.repo.environment_repo import IEnvironmentRepo
from cicada.domain.repository import RepositoryId


class EnvironmentRepo(IEnvironmentRepo, DbConnection):
    def get_env_var_for_repo(self, id: RepositoryId, key: str) -> EnvironmentVariable | None:
        rows = self.conn.execute(
            "SELECT key, value FROM env_vars WHERE repo_id=? AND key=?",
            [id, key],
        ).fetchall()

        if not rows:
            return None

        return EnvironmentVariable(key=rows[0]["key"], value=rows[0]["value"])

    def get_env_vars_for_repo(self, id: RepositoryId) -> list[EnvironmentVariable]:
        rows = self.conn.execute(
            """
            SELECT key, value
            FROM env_vars
            WHERE repo_id=?
            ORDER BY "order";
            """,
            [id],
        ).fetchall()

        return [EnvironmentVariable(*row) for row in rows]

    def set_env_vars_for_repo(self, id: RepositoryId, env_vars: list[EnvironmentVariable]) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM env_vars WHERE repo_id=?", [id])

            self.conn.executemany(
                """
                INSERT INTO env_vars (repo_id, key, value, "order")
                VALUES (?, ?, ?, ?)
                ON CONFLICT DO UPDATE SET value=?
                """,
                [
                    (
                        id,
                        env_var.key,
                        env_var.value,
                        order,
                        env_var.value,
                    )
                    for order, env_var in enumerate(env_vars)
                ],
            )
