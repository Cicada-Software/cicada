import re

import pytest

from cicada.domain.cache import CacheKey


def test_invalid_cache_keys_detected() -> None:
    invalid_char = "Cache key cannot contain any of the following"

    tests = {
        "": "Cache key cannot be empty",
        "x" * 267: "Cache key cannot be greater than 256 characters",
        ":": invalid_char,
        '"': invalid_char,
        "'": invalid_char,
        "<": invalid_char,
        ">": invalid_char,
        "&": invalid_char,
        "+": invalid_char,
        "=": invalid_char,
        "/": invalid_char,
        "\\": invalid_char,
    }

    for key, error in tests.items():
        with pytest.raises(ValueError, match=error):
            CacheKey(key)


def test_invalid_cache_key_invalid_char_error_message() -> None:
    expected = r"""
Cache key cannot contain any of the following characters: ":\"'<>&+=/\"
"""

    with pytest.raises(ValueError, match=re.escape(expected.strip())):
        CacheKey("/")
