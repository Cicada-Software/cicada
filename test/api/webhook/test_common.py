from cicada.api.endpoints.webhook.common import is_repo_in_white_list


def test_empty_whitelist_returns_false() -> None:
    assert not is_repo_in_white_list("user/repo", [])


def test_repo_not_matching_regex_returns_false() -> None:
    assert not is_repo_in_white_list("a/repo", ["b/.*"])


def test_repo_matching_regex_returns_true() -> None:
    assert is_repo_in_white_list("a/repo", ["a/.*"])


def test_repo_matching_string_returns_true() -> None:
    assert is_repo_in_white_list("a/repo", ["a/repo"])
