import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography.fernet import Fernet

from cicada.api.infra.db_connection import DbConnection
from cicada.api.settings import GitlabSettings
from cicada.domain.user import User


@dataclass(kw_only=True)
class Token:
    access_token: str
    expires_at: int
    refresh_token: str

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


class GitlabOAuthTokenStore(DbConnection):
    """
    Securely store Gitlab OAuth tokens. Because Gitlab does not allow authenticating via an OAuth
    application you need to hold on to users' OAuth tokens. This API allows for securely storing,
    refreshing, and accessing user tokens.
    """

    tokens: dict[str, Token]
    fernet: Fernet

    def __init__(self) -> None:
        super().__init__()

        self.tokens = {}
        self.settings = GitlabSettings()

        self.fernet = Fernet(self.settings.token_store_secret.encode())

    def save_token(self, user: User, token: Token) -> None:
        assert user.provider == "gitlab"

        self.tokens[user.username] = token

        data = json.dumps([token.access_token, token.refresh_token], separators=(",", ":"))

        cipher = self.fernet.encrypt(data.encode())

        self.conn.execute(
            """
            INSERT INTO gitlab_oauth_tokens (user_id, expires_at, data)
            VALUES ((SELECT id FROM users WHERE uuid=?), ?, ?)
            ON CONFLICT DO UPDATE SET expires_at=excluded.expires_at, data=excluded.data;
            """,
            [user.id, token.expires_at, cipher],
        )

        self.conn.commit()

    async def load_token(self, user: User) -> Token | None:
        assert user.provider == "gitlab"

        token = self.tokens.get(user.username)

        if not token:
            row = self.conn.execute(
                """
                SELECT data, expires_at
                FROM gitlab_oauth_tokens
                WHERE user_id=(SELECT id FROM users WHERE uuid=?);
                """,
                [user.id],
            ).fetchone()

            if not row:
                return None

            expires_at = row["expires_at"]

            plaintext = self.fernet.decrypt(row["data"])
            [access_token, refresh_token] = json.loads(plaintext)

            token = Token(
                access_token=access_token, expires_at=expires_at, refresh_token=refresh_token
            )

        token = await self._refresh_token(token) if token.expired else token

        self.save_token(user, token)

        return token

    @staticmethod
    def oauth_response_to_token(data: dict[str, Any]) -> Token:  # type: ignore
        return Token(
            access_token=data["access_token"],
            expires_at=data["created_at"] + data["expires_in"],
            refresh_token=data["refresh_token"],
        )

    async def _refresh_token(self, token: Token) -> Token:
        params = {
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
            "refresh_token": token.refresh_token,
            "grant_type": "refresh_token",
            "redirect_uri": self.settings.redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post("https://gitlab.com/oauth/token", params=params)

        data = resp.json()

        return self.oauth_response_to_token(data)
