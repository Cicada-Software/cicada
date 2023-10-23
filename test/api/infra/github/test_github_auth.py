from uuid import uuid4

from cicada.api.infra.github.auth import (
    create_or_update_github_installation,
    create_or_update_github_user,
    update_github_repo_perms,
)
from cicada.domain.installation import Installation, InstallationScope
from cicada.domain.user import User
from test.api.endpoints.common import TestDiContainer
from test.common import build


def test_github_user_repo_perms_caching() -> None:
    di = TestDiContainer()
    di.reset()

    repo_url = "https://github.com/new_user/repo"

    event = {
        "sender": {
            "type": "User",
            "login": "new_user",
        },
        "repository": {
            "owner": {"login": "new_user"},
            "html_url": repo_url,
            "private": True,
        },
    }

    user = create_or_update_github_user(di.user_repo(), event)
    assert user

    update_github_repo_perms(di, user.id, event, "any event")

    # Check user/repo binding was automatically created
    assert di.connection
    rows = di.connection.execute("SELECT user_id, repo_id, perms FROM _user_repos").fetchall()

    assert len(rows) == 1

    user_id, repo_id, perms = rows[0]

    assert isinstance(user_id, int)
    assert isinstance(repo_id, int)
    assert perms == "owner"

    # Check user was automatically created
    users = di.connection.execute(
        """
        SELECT uuid, username, platform FROM users WHERE id=?
        """,
        [user_id],
    ).fetchall()

    assert len(users) == 1

    assert users[0][0] == str(user.id)
    assert users[0][1] == "new_user"
    assert users[0][2] == "github"

    # Check repository was automatically created
    repo = di.repository_repo().get_repository_by_repo_id(repo_id)

    assert repo

    assert repo.id
    assert repo.url == repo_url
    assert repo.provider == "github"
    assert not repo.is_public


def test_no_new_entries_for_the_same_repository() -> None:
    di = TestDiContainer()
    di.reset()

    repo_url = "https://github.com/new_user/repo"

    event = {
        "sender": {
            "type": "User",
            "login": "new_user",
        },
        "repository": {
            "owner": {"login": "new_user"},
            "html_url": repo_url,
            "private": True,
        },
    }

    user = create_or_update_github_user(di.user_repo(), event)
    assert user

    update_github_repo_perms(di, user.id, event, "any event")

    assert di.connection

    user_id = di.connection.execute("SELECT uuid FROM users WHERE username='new_user'").fetchone()[
        0
    ]

    update_github_repo_perms(di, user_id, event, "any event")

    new_user_id = di.connection.execute(
        "SELECT uuid FROM users WHERE username='new_user'"
    ).fetchone()[0]

    assert user_id == new_user_id

    rows = di.connection.execute("SELECT * FROM _user_repos").fetchall()

    assert len(rows) == 1


def test_invalid_events_are_ignored() -> None:
    di = TestDiContainer()
    di.reset()

    update_github_repo_perms(di, uuid4(), {}, "any event")
    update_github_repo_perms(di, uuid4(), {"sender": {}}, "any event")
    update_github_repo_perms(di, uuid4(), {"sender": {"type": "Robot"}}, "any event")
    update_github_repo_perms(di, uuid4(), {"sender": {"type": "User"}}, "any event")

    event = {
        "sender": {
            "type": "User",
            "login": "user A",
        },
        "repository": {
            "owner": {"login": "user B"},
        },
    }

    update_github_repo_perms(di, uuid4(), event, "any event")

    assert di.connection
    rows = di.connection.execute("SELECT * FROM _user_repos").fetchall()

    assert not rows


def test_auto_deduce_perms_from_event_type() -> None:
    di = TestDiContainer()
    di.reset()

    event = {
        "sender": {
            "type": "User",
            "login": "sender",
        },
        "repository": {
            "owner": {"login": "owner"},
            "html_url": "some url",
            "private": True,
        },
    }

    event_types = {
        "push": "write",
        "issues": "read",
    }

    for event_type, perm in event_types.items():
        user = create_or_update_github_user(di.user_repo(), event)
        assert user

        update_github_repo_perms(di, user.id, event, event_type)

        assert di.connection
        rows = di.connection.execute(
            """
            SELECT ur.perms, u.username FROM _user_repos ur
            JOIN users u ON u.id = ur.user_id
            """
        ).fetchall()

        assert len(rows) == 1

        user_perms, username = rows[0]

        assert user_perms == perm
        assert username == "sender"


def test_create_installation() -> None:
    di = TestDiContainer()
    di.reset()

    user = build(User, username="bob", provider="github")

    di.user_repo().create_or_update_user(user)

    event = {
        "action": "added",
        "installation": {
            "account": {"login": "username"},
            "target_type": "User",
            "html_url": "url",
            "id": "1337",
        },
    }

    create_or_update_github_installation(di, user.id, event)

    installation_repo = di.installation_repo()

    installations = installation_repo.get_installations_for_user(user)

    assert len(installations) == 1

    installation = installations[0]

    assert installation == Installation(
        id=installation.id,
        name="username",
        provider="github",
        scope=InstallationScope.USER,
        admin_id=user.id,
        provider_id="1337",
        provider_url="url",
    )

    # test re-adding installation doesnt create new installation
    create_or_update_github_installation(di, user.id, event)

    installations = installation_repo.get_installations_for_user(user)

    assert len(installations) == 1
    assert installations[0] == installation
