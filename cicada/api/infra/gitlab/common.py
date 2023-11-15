from dataclasses import dataclass
from typing import cast

from gitlab import Gitlab


def gitlab_clone_url(user: str, repo: str, access_token: str) -> str:
    return f"https://oauth2:{access_token}@gitlab.com/{user}/{repo}.git"


@dataclass
class GitlabProject:
    id: int
    path: str
    description: str | None


def get_authenticated_user_id(gl: Gitlab) -> int:
    if gl.user is None:
        gl.auth()

    assert gl.user

    return cast(int, gl.user.asdict()["id"])


def get_projects_for_user(gl: Gitlab, user_id: int) -> list[GitlabProject]:
    projects = gl.users.get(user_id, lazy=True).projects.list(simple=True, get_all=True)

    return [
        GitlabProject(
            id=project.id,
            path=project.path_with_namespace,
            description=project.description,
        )
        for project in projects
    ]
