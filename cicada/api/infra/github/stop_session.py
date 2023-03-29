from cicada.api.common.datetime import UtcDatetime
from cicada.api.common.http import url_get_user_and_repo
from cicada.api.domain.session import Session
from cicada.api.domain.triggers import CommitTrigger
from cicada.api.infra.github.common import get_github_integration_for_repo


async def github_session_terminator(session: Session) -> None:
    if not isinstance(session.trigger, CommitTrigger):
        return

    username, repo_name = url_get_user_and_repo(session.trigger.repository_url)

    github = await get_github_integration_for_repo(username, repo_name)

    data = await github.rest.checks.async_list_for_ref(
        username,
        repo_name,
        str(session.trigger.sha),
        check_name="Cicada",
    )

    for check in data.parsed_data.check_runs:
        await github.rest.checks.async_update(
            username,
            repo_name,
            check.id,
            status="completed",
            conclusion="cancelled",
            completed_at=UtcDatetime.now(),
        )
