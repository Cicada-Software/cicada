import pytest

from cicada.domain.secret import Secret


def test_key_cannot_be_empty() -> None:
    with pytest.raises(ValueError, match="Key cannot be empty"):
        Secret("", "value")


def test_key_cannot_be_too_long() -> None:
    # Max len is ok
    Secret(key="x" * Secret.MAX_KEY_LEN, value="")

    with pytest.raises(ValueError, match="Key is too long"):
        Secret(key="x" * (Secret.MAX_KEY_LEN + 1), value="")


def test_key_must_match_pattern() -> None:
    tests = {
        "ABC": True,
        "abc": True,
        "API_KEY": True,
        "_API_KEY": True,
        "API_KEY_0": True,
        "API.KEY": False,
        "123": False,
        "WHITE SPACE": False,
        " LEADING_WHITESPACE": False,
        "TRAILING_WHITESPACE ": False,
    }

    for key, is_valid in tests.items():
        if is_valid:
            Secret(key, "")

        else:
            with pytest.raises(ValueError, match="Key does not match regex"):
                Secret(key, "")


def test_value_cannot_be_too_long() -> None:
    # Max len is ok
    Secret("KEY", "x" * Secret.MAX_VALUE_LEN)

    with pytest.raises(ValueError, match="Value is too long"):
        Secret("KEY", "x" * (Secret.MAX_VALUE_LEN + 1))
