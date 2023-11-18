from typing import Any

from cicada.domain.datetime import Datetime
from cicada.domain.triggers import (
    CommitTrigger,
    GitSha,
    IssueCloseTrigger,
    IssueOpenTrigger,
    IssueTrigger,
)


def github_event_to_commit(event: dict[str, Any]) -> CommitTrigger:  # type: ignore[misc]
    return CommitTrigger(
        sha=GitSha(event["after"]),
        author=event["head_commit"]["author"].get("username"),
        message=event["head_commit"]["message"],
        committed_on=Datetime.fromisoformat(event["head_commit"]["timestamp"]),
        repository_url=event["repository"]["html_url"],
        provider="github",
        ref=event["ref"],
        default_branch=event["repository"]["default_branch"],
    )


def github_event_to_issue(event: dict[str, Any]) -> IssueTrigger:  # type: ignore[misc]
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
        "default_branch": event["repository"]["default_branch"],
    }

    if event["action"] == "opened":
        return IssueOpenTrigger(**data)

    if event["action"] == "closed":
        data["closed_at"] = Datetime.fromisoformat(event["issue"]["closed_at"])

        return IssueCloseTrigger(**data)

    assert False
