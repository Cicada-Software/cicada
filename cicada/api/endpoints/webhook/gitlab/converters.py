from typing import Any

from cicada.api.common.datetime import Datetime
from cicada.api.domain.triggers import (
    CommitTrigger,
    GitSha,
    IssueCloseTrigger,
    IssueOpenTrigger,
    IssueTrigger,
)


def gitlab_event_to_commit(  # type: ignore
    event: dict[str, Any]
) -> CommitTrigger:
    most_recent_commit: None | dict[str, Any] = None  # type: ignore

    for json_commit in event["commits"]:
        if json_commit["id"] == event["after"]:
            most_recent_commit = json_commit
            break

    # This shouldn't happen
    assert most_recent_commit

    return CommitTrigger(
        sha=GitSha(event["after"]),
        author=event["user_username"],
        # TODO: message includes newlines, possibly strip() it?
        message=most_recent_commit["message"],
        committed_on=Datetime.fromisoformat(most_recent_commit["timestamp"]),
        repository_url=event["repository"]["homepage"],
        provider="gitlab",
        ref=event["ref"],
    )


def gitlab_event_to_issue(  # type: ignore
    event: dict[str, Any]
) -> IssueTrigger:
    data = {
        "id": str(event["object_attributes"]["iid"]),
        "title": event["object_attributes"]["title"],
        "sha": None,
        "submitted_by": event["user"]["name"],
        "is_locked": bool(event["object_attributes"]["discussion_locked"]),
        "opened_at": Datetime.fromisoformat(
            event["object_attributes"]["created_at"]
        ),
        "body": event["object_attributes"]["description"],
        "repository_url": event["repository"]["homepage"],
        "provider": "gitlab",
    }

    if "created_at" in event["changes"]:
        return IssueOpenTrigger(**data)

    if "closed_at" in event["changes"]:
        closed_at = Datetime.fromisoformat(
            event["object_attributes"]["closed_at"]
        )

        return IssueCloseTrigger(**data, closed_at=closed_at)

    assert False
