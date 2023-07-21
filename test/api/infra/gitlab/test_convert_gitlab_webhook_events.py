import json
from pathlib import Path

from cicada.api.endpoints.webhook.gitlab.converters import (
    gitlab_event_to_commit,
    gitlab_event_to_issue,
)
from cicada.domain.datetime import Datetime
from cicada.domain.triggers import (
    CommitTrigger,
    GitSha,
    IssueCloseTrigger,
    IssueOpenTrigger,
)


def test_convert_issue_open_event() -> None:
    data = json.loads(
        Path("test/api/infra/gitlab/test_data/issue_open.json").read_text()
    )

    event = gitlab_event_to_issue(data)

    body = """\
This is the body of the issue.

Here is some code:

```python
print("Hello from gitlab!")
```"""

    assert event == IssueOpenTrigger(
        id="1",
        provider="gitlab",
        repository_url="https://gitlab.com/dosisod/cicada-testing2",
        title="Gitlab issue test",
        submitted_by="dosisod",
        is_locked=False,
        opened_at=Datetime.fromisoformat("2022-12-13 19:16:27 UTC"),
        body=body,
        sha=None,
    )


def test_convert_issue_close_event() -> None:
    data = json.loads(
        Path("test/api/infra/gitlab/test_data/issue_close.json").read_text()
    )

    event = gitlab_event_to_issue(data)

    assert event == IssueCloseTrigger(
        id="6",
        provider="gitlab",
        repository_url="https://gitlab.com/dosisod/cicada-testing2",
        title="Test new Gitlab issue handler",
        submitted_by="dosisod",
        is_locked=False,
        body="",
        opened_at=Datetime.fromisoformat("2023-02-05 21:26:55 UTC"),
        closed_at=Datetime.fromisoformat("2023-02-05 21:27:17 UTC"),
        sha=None,
    )


def test_convert_git_push_event() -> None:
    data = json.loads(
        Path("test/api/infra/gitlab/test_data/git_push.json").read_text()
    )

    event = gitlab_event_to_commit(data)

    assert event == CommitTrigger(
        sha=GitSha("7be3fc13b643d4fa0312a613d8bd48fa091b1b49"),
        repository_url="https://gitlab.com/dosisod/cicada-testing2",
        author="dosisod",
        message="Split up and test run_program\n",
        committed_on=Datetime.fromisoformat("2022-12-02T12:22:05-08:00"),
        ref="refs/heads/master",
        provider="gitlab",
    )
