# Copied from: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt

from contextlib import suppress
from datetime import timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException

from cicada.api.endpoints.di import Di, JWTToken
from cicada.api.settings import JWTSettings
from cicada.domain.datetime import UtcDatetime
from cicada.domain.repo.user_repo import IUserRepo
from cicada.domain.user import User


def create_jwt(  # type: ignore[misc]
    *,
    subject: str,
    issuer: str,
    audience: str | None = None,
    data: dict[str, Any] | None = None,
) -> str:
    settings = JWTSettings()

    now = UtcDatetime.now()
    delta = timedelta(seconds=settings.expiration_timeout)

    audience = audience or settings.domain

    payload = {
        **(data or {}),
        "iat": now,
        "exp": now + delta,
        "sub": subject,
        "iss": issuer,
        "aud": audience,
    }

    return jwt.encode(payload, settings.secret, algorithm="HS256")


IDENTITY_PROVIDERS = ("github", "gitlab", "cicada")


def get_user_and_payload_from_jwt(  # type: ignore[misc]
    user_repo: IUserRepo, token: str
) -> tuple[User, dict[str, Any]] | None:
    settings = JWTSettings()

    with suppress(jwt.PyJWTError):
        payload = jwt.decode(
            jwt=token,
            key=settings.secret,
            audience=settings.domain,
            algorithms=["HS256"],
        )

        username: str = payload.get("sub", "")
        provider: str = payload.get("iss", "")

        assert provider in IDENTITY_PROVIDERS

        user = user_repo.get_user_by_username_and_provider(username, provider=provider)

        if not user:
            return None

        user.password_hash = None

        return user, payload

    return None


def get_user_from_jwt(user_repo: IUserRepo, token: str) -> User | None:
    if data := get_user_and_payload_from_jwt(user_repo, token):
        return data[0]

    return None


def get_current_user(di: Di, token: JWTToken) -> User:
    if user := get_user_from_jwt(di.user_repo(), token):
        return user

    raise HTTPException(
        status_code=401,
        detail="JWT Invalid",
        headers={"WWW-Authenticate": "Bearer"},
    )


CurrentUser = Annotated[User, Depends(get_current_user)]


def create_access_token(  # type: ignore[misc]
    user: User, issuer: str = "cicada"
) -> dict[str, Any]:
    jwt = create_jwt(subject=user.username, issuer=issuer)

    return {"access_token": jwt}
