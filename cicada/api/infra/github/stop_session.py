from cicada.api.infra.common import url_get_user_and_repo
from cicada.api.infra.github.common import get_github_integration_for_repo
from cicada.domain.datetime import UtcDatetime
from cicada.domain.session import Session, Workflow
from cicada.domain.triggers import CommitTrigger


async def github_session_terminator(session: Session) -> None:
    if not isinstance(session.trigger, CommitTrigger):
        return

    username, repo_name = url_get_user_and_repo(session.trigger.repository_url)

    github = await get_github_integration_for_repo(username, repo_name)

    data = await github.rest.checks.async_list_for_ref(
        username,
        repo_name,
        str(session.trigger.sha),
        app_id=int(github.auth.app_id),
    )

    possible_external_ids = set[str]()

    def add_workflow_ids(workflow: Workflow) -> None:
        possible_external_ids.add(str(workflow.id))

        for sub_workflow in workflow.sub_workflows:
            add_workflow_ids(sub_workflow)

    add_workflow_ids(session.runs[session.run - 1])

    for check in data.parsed_data.check_runs:
        if check.status == "in_progress" and str(check.external_id) in possible_external_ids:
            await github.rest.checks.async_update(
                username,
                repo_name,
                check.id,
                status="completed",
                conclusion="cancelled",
                completed_at=UtcDatetime.now(),
            )
