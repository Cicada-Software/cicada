import re


def is_repo_in_white_list(repo: str, white_list: list[str]) -> bool:
    """
    This white list is a bandaid for the fact that using Docker is not secure
    for running untrusted code as root. By only allowing certain users/repos,
    we can make sure that (at least) random people dont try and pwn our host.
    This is a temporary fix, and a more robust solution is in the works.
    """

    return any(re.match(name, repo) for name in white_list)
