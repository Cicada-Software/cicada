import pytest
from fastapi import HTTPException

from cicada.api.endpoints.csrf import CsrfTokenCache


def test_generate_and_validate_token() -> None:
    cache = CsrfTokenCache()
    assert not cache.tokens

    token = cache.generate()
    assert token in cache.tokens

    cache.validate(token)
    assert token not in cache.tokens


def test_validate_token_fails_if_nonexistent() -> None:
    cache = CsrfTokenCache()

    with pytest.raises(HTTPException, match="validation failure"):
        cache.validate("nonexistent")


def test_validate_token_fails_if_expired() -> None:
    class TestCache(CsrfTokenCache):
        DEFAULT_EXPIRATION_IN_SECONDS = 0

    cache = TestCache()

    token = cache.generate()

    with pytest.raises(HTTPException, match="expired"):
        cache.validate(token)
