import logging
import time
from secrets import token_hex

from fastapi import HTTPException


class CsrfTokenCache:
    """
    An in-memory CSRF token cache. This class has 2 operations: generate and validate. When you
    generate a token it will be stored along with the timestamp when it was created. When you
    validate, the token will be popped, and the timestamp will be compared. If the token does not
    exist or has expired, an HTTPException is thrown. In addition, if the token did not exist, a
    logger message is emitted since a nonexistent CSRF token is either a bug or an attacker trying
    to forge a token, which should be investigated.
    """

    tokens: dict[str, float]

    DEFAULT_EXPIRATION_IN_SECONDS = 5 * 60

    def __init__(self) -> None:
        self.tokens = {}

    def generate(self) -> str:
        token = token_hex(16)
        self.tokens[token] = time.time()

        return token

    def validate(self, token: str) -> None:
        expiration = self.tokens.pop(token, None)

        if expiration is None:
            msg = "CSRF token validation failure"

            logger = logging.getLogger("cicada")
            logger.warning(msg)

            raise HTTPException(401, msg) from None

        if time.time() > (expiration + self.DEFAULT_EXPIRATION_IN_SECONDS):
            raise HTTPException(401, "CSRF token expired")
