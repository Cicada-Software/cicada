import re

URL_REGEX = re.compile("https://[^/]+/([^/]+)/([^/]+)")


def url_get_user_and_repo(url: str) -> tuple[str, str]:
    return URL_REGEX.search(url).groups()  # type: ignore
