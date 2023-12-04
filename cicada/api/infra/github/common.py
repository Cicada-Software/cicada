from functools import cache
from pathlib import Path

from githubkit import AppAuthStrategy, AppInstallationAuthStrategy, GitHub

from cicada.api.infra.common import url_get_user_and_repo
from cicada.api.infra.repo_get_ci_files import repo_get_ci_files
from cicada.api.settings import GitHubSettings
from cicada.ast.generate import AstError
from cicada.ast.nodes import FileNode
from cicada.domain.datetime import UtcDatetime
from cicada.domain.triggers import Trigger


@cache
def get_github_integration() -> GitHub[AppAuthStrategy]:
    settings = GitHubSettings()

    return GitHub(
        AppAuthStrategy(
            str(settings.app_id),
            settings.key_file.read_text(),
            settings.client_id,
            settings.client_secret,
        )
    )


INSTALLATION_IDS: dict[str, int] = {}


async def get_installation_id(user: str, repo: str) -> int:
    # TODO: what happens when an installation is uninstalled/reinstalled, thus
    # changing the installation ID?

    slug = f"{user}/{repo}"

    if id := INSTALLATION_IDS.get(slug):
        return id

    github = get_github_integration()

    resp = await github.rest.apps.async_get_repo_installation(user, repo)

    id = resp.parsed_data.id
    INSTALLATION_IDS[slug] = id

    return id


async def get_github_integration_for_repo(
    user: str, repo: str
) -> GitHub[AppInstallationAuthStrategy]:
    installation_id = await get_installation_id(user, repo)

    github = get_github_integration()

    return GitHub(github.auth.as_installation(installation_id))


async def create_access_token_from_repository_url(url: str) -> str:
    username, repo = url_get_user_and_repo(url)

    return await get_repo_access_token(username, repo)


async def get_repo_access_token(user: str, repo: str) -> str:
    # TODO: managing the permissions for this token is very important, and will
    # probably need to be updated as time goes on. Burying these permissions in
    # this function is probably not the best idea.

    installation_id = await get_installation_id(user, repo)

    github = get_github_integration()

    data = await github.rest.apps.async_create_installation_access_token(
        installation_id,
        data={
            "repositories": [repo],
            "permissions": {
                "contents": "read",
                "checks": "write",
            },
        },
    )

    return data.parsed_data.token


async def add_access_token_for_repository_url(url: str) -> str:
    username, repo = url_get_user_and_repo(url)
    access_token = await get_repo_access_token(username, repo)

    return github_clone_url(username, repo, access_token)


def github_clone_url(user: str, repo: str, access_token: str) -> str:
    return f"https://{access_token}:{access_token}@github.com/{user}/{repo}"


async def gather_workflows_via_trigger(
    trigger: Trigger,
    cloned_repo: Path,
) -> list[FileNode]:
    assert trigger.sha

    started_at = UtcDatetime.now()

    username, repo_name = url_get_user_and_repo(trigger.repository_url)

    access_token = await get_repo_access_token(username, repo_name)

    url = github_clone_url(username, repo_name, access_token)

    files_or_errors = await repo_get_ci_files(
        url,
        str(trigger.sha),
        trigger,
        cloned_repo,
    )

    errors = [x for x in files_or_errors if isinstance(x, AstError)]

    if errors:
        annotations = [ast_error_to_github_annotation(x) for x in errors]

        github = GitHub(access_token)

        await github.rest.checks.async_create(
            username,
            repo_name,
            data={
                "name": "Cicada CI File Validator",
                "head_sha": str(trigger.sha),
                # This doesnt seem right IMO
                "external_id": str(trigger.sha),
                "status": "completed",
                "conclusion": "failure",
                "started_at": started_at,
                "completed_at": UtcDatetime.now(),
                "output": {
                    "title": "Cicada CI File Validator",
                    "summary": "One or more `.ci` files contained a syntax error",
                    "annotations": annotations,  # type: ignore[call-overload]
                },
            },
        )

    return [x for x in files_or_errors if not isinstance(x, AstError)]


def ast_error_to_github_annotation(error: AstError) -> dict[str, str | int]:
    return {
        "annotation_level": "failure",
        "title": "Syntax Error",
        "path": error.filename or "",
        "start_line": error.line,
        "end_line": error.line,
        "start_column": error.column,
        "message": error.msg,
    }
