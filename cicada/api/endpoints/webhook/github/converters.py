from typing import Any

from cicada.api.common.datetime import Datetime
from cicada.api.domain.triggers import (
    CommitTrigger,
    GitSha,
    IssueCloseTrigger,
    IssueOpenTrigger,
    IssueTrigger,
)


def github_event_to_commit(  # type: ignore[misc]
    event: dict[str, Any]
) -> CommitTrigger:
    return CommitTrigger(
        sha=GitSha(event["after"]),
        author=event["head_commit"]["author"]["name"],
        message=event["head_commit"]["message"],
        committed_on=Datetime.fromisoformat(event["head_commit"]["timestamp"]),
        repository_url=event["repository"]["html_url"],
        provider="github",
        ref=event["ref"],
    )


def github_event_to_issue(  # type: ignore[misc]
    event: dict[str, Any]
) -> IssueTrigger:
    data = {
        "id": str(event["issue"]["number"]),
        "sha": None,
        "title": event["issue"]["title"],
        "submitted_by": event["issue"]["user"]["login"],
        "is_locked": event["issue"]["locked"],
        "opened_at": Datetime.fromisoformat(event["issue"]["created_at"]),
        "body": event["issue"]["body"] or "",
        "repository_url": event["repository"]["html_url"],
        "provider": "github",
    }

    if event["action"] == "opened":
        return IssueOpenTrigger(**data)

    if event["action"] == "closed":
        data["closed_at"] = Datetime.fromisoformat(event["issue"]["closed_at"])

        return IssueCloseTrigger(**data)

    assert False
