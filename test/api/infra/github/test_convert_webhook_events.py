import json
from pathlib import Path

from cicada.api.common.datetime import Datetime
from cicada.api.domain.triggers import (
    CommitTrigger,
    GitSha,
    IssueCloseTrigger,
    IssueOpenTrigger,
)
from cicada.api.endpoints.webhook.github.converters import (
    github_event_to_commit,
    github_event_to_issue,
)

TEST_DATA = Path(__file__).parent / "test_data"


def test_convert_commit_event() -> None:
    event = json.loads((TEST_DATA / "push_event.json").read_text())
    commit = github_event_to_commit(event)

    assert commit == CommitTrigger(
        sha=GitSha("d585fb410128c9970c55102e887a509cdee943c2"),
        ref="refs/heads/master",
        author="dosisod",
        message="Add experimental Cicada CI runner",
        committed_on=Datetime.fromisoformat("2022-12-12T14:18:02-08:00"),
        repository_url="https://github.com/dosisod/ci-test-stuff",
        provider="github",
    )


def test_convert_issue_open_event() -> None:
    event = json.loads((TEST_DATA / "issue_open_event.json").read_text())
    issue = github_event_to_issue(event)

    body = """\
This is the body of the issue

Code block:

```python
print("hello world!")
```"""

    body = body.replace("\n", "\r\n")

    assert issue == IssueOpenTrigger(
        id="1",
        title="Testing Issue Webhook",
        submitted_by="dosisod",
        is_locked=False,
        opened_at=Datetime.fromisoformat("2022-12-13T18:52:06+00:00"),
        body=body,
        repository_url="https://github.com/dosisod/cicada-testing2",
        provider="github",
        sha=None,
    )


def test_convert_issue_close_event() -> None:
    event = json.loads((TEST_DATA / "issue_close_event.json").read_text())
    issue = github_event_to_issue(event)

    body = """\
This is the body of the issue

Code block:

```python
print("hello world!")
```"""

    body = body.replace("\n", "\r\n")

    assert issue == IssueCloseTrigger(
        id="1",
        title="Testing Issue Webhook",
        submitted_by="dosisod",
        is_locked=False,
        opened_at=Datetime.fromisoformat("2022-12-13T18:52:06+00:00"),
        body=body,
        repository_url="https://github.com/dosisod/cicada-testing2",
        provider="github",
        closed_at=Datetime.fromisoformat("2023-02-03T06:06:15Z"),
        sha=None,
    )
