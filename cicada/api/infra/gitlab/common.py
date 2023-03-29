def gitlab_clone_url(user: str, repo: str, access_token: str) -> str:
    return f"https://gitlab-ci-token:{access_token}@gitlab.com/{user}/{repo}"
