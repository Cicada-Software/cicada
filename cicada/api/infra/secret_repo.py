import sqlite3
from base64 import b64decode, b64encode

from cicada.api.infra.db_connection import DbConnection
from cicada.api.infra.vault import get_vault_client
from cicada.domain.datetime import UtcDatetime
from cicada.domain.installation import InstallationId
from cicada.domain.repo.secret_repo import ISecretRepo
from cicada.domain.repository import RepositoryId
from cicada.domain.secret import Secret


class SecretRepo(ISecretRepo, DbConnection):
    def __init__(self, db: sqlite3.Connection | None = None) -> None:
        super().__init__(db)

        self.client = get_vault_client()

    def list_secrets_for_repo(self, id: RepositoryId) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT key
            FROM secrets
            WHERE scope='r' AND repo_id=?;
            """,
            [id],
        ).fetchall()

        return [row[0] for row in rows]

    def list_secrets_for_installation(self, id: InstallationId) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT key
            FROM secrets
            WHERE scope='i' AND installation_uuid=?;
            """,
            [id],
        ).fetchall()

        return [row[0] for row in rows]

    def get_secrets_for_repo(self, id: RepositoryId) -> list[Secret]:
        rows = self.conn.execute(
            """
            SELECT key, ciphertext, updated_at
            FROM secrets
            WHERE scope='r' AND repo_id=?;
            """,
            [id],
        ).fetchall()

        if not rows:
            return []

        keys = [x[0] for x in rows]
        updated_at = [UtcDatetime.fromisoformat(x[2]) for x in rows]

        values = self._decrypt(
            key=self._repo_key_name(id),
            data=[x[1] for x in rows],
        )

        return [Secret(key=k, value=v, updated_at=u) for k, v, u in zip(keys, values, updated_at)]

    def get_secrets_for_installation(self, id: InstallationId) -> list[Secret]:
        rows = self.conn.execute(
            """
            SELECT key, ciphertext, updated_at
            FROM secrets
            WHERE scope='i' AND installation_uuid=?;
            """,
            [id],
        ).fetchall()

        if not rows:
            return []

        keys = [x[0] for x in rows]

        values = self._decrypt(
            key=self._installation_key_name(id),
            data=[x[1] for x in rows],
        )

        updated_at = [UtcDatetime.fromisoformat(x[2]) for x in rows]

        return [Secret(key=k, value=v, updated_at=u) for k, v, u in zip(keys, values, updated_at)]

    def set_secrets_for_repo(self, id: RepositoryId, secrets: list[Secret]) -> None:
        keys = [s.key for s in secrets]

        ciphers = self._encrypt(
            key=self._repo_key_name(id),
            data=[s.value for s in secrets],
        )

        updated_at = [s.updated_at for s in secrets]

        self.conn.executemany(
            """
            INSERT INTO secrets (
                scope,
                repo_id,
                updated_at,
                key,
                ciphertext
            )
            VALUES ('r', ?, ?, ?, ?)
            ON CONFLICT DO UPDATE SET
                ciphertext=excluded.ciphertext,
                updated_at=excluded.updated_at
            """,
            [[id, u, k, v] for u, k, v in zip(updated_at, keys, ciphers)],
        )

        self.conn.commit()

    def set_secrets_for_installation(self, id: InstallationId, secrets: list[Secret]) -> None:
        keys = [s.key for s in secrets]

        ciphers = self._encrypt(
            key=self._installation_key_name(id),
            data=[s.value for s in secrets],
        )

        updated_at = [s.updated_at for s in secrets]

        self.conn.executemany(
            """
            INSERT INTO secrets (
                scope,
                installation_uuid,
                updated_at,
                key,
                ciphertext
            )
            VALUES ('i', ?, ?, ?, ?)
            ON CONFLICT DO UPDATE SET
                ciphertext=excluded.ciphertext,
                updated_at=excluded.updated_at
            """,
            [[id, u, k, v] for u, k, v in zip(updated_at, keys, ciphers)],
        )

        self.conn.commit()

    def delete_repository_secret(self, id: RepositoryId, key: str) -> None:
        self.conn.execute(
            """
            DELETE FROM secrets
            WHERE scope='r' AND repo_id=? AND key=?;
            """,
            [id, key],
        )

        self.conn.commit()

    def delete_installation_secret(self, id: InstallationId, key: str) -> None:
        self.conn.execute(
            """
            DELETE FROM secrets
            WHERE scope='i' AND installation_uuid=? AND key=?;
            """,
            [id, key],
        )

        self.conn.commit()

    def _encrypt(self, key: str, data: list[str]) -> list[str]:
        # Create key if it doesn't already exist
        self.client.secrets.transit.create_key(key, auto_rotate_period="30d")

        plaintexts = [{"plaintext": b64encode(x.encode()).decode()} for x in data]

        resp = self.client.secrets.transit.encrypt_data(key, batch_input=plaintexts)

        return [b["ciphertext"] for b in resp["data"]["batch_results"]]

    def _decrypt(self, key: str, data: list[str]) -> list[str]:
        ciphers = [{"ciphertext": x} for x in data]

        resp = self.client.secrets.transit.decrypt_data(key, batch_input=ciphers)

        return [b64decode(b["plaintext"]).decode() for b in resp["data"]["batch_results"]]

    @staticmethod
    def _installation_key_name(id: InstallationId) -> str:
        return f"installation_{id}"

    @staticmethod
    def _repo_key_name(id: RepositoryId) -> str:
        return f"repository_{id}"
