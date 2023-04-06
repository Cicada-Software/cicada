from cicada.api.infra.github.auth import update_github_repo_perms
from test.api.endpoints.common import TestDiContainer


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
        },
    }

    update_github_repo_perms(di, event, "any event")

    assert di.connection
    rows = di.connection.execute(
        "SELECT user_id, repo_id, perms FROM _user_repos"
    ).fetchall()

    assert len(rows) == 1

    user_id, repo_id, perms = rows[0]

    assert isinstance(user_id, int)
    assert isinstance(repo_id, int)
    assert perms == "owner"

    users = di.connection.execute(
        "SELECT username, platform FROM users WHERE id=?", [user_id]
    ).fetchall()

    assert len(users) == 1

    assert users[0][0] == "new_user"
    assert users[0][1] == "github"

    repos = di.connection.execute(
        "SELECT url FROM repositories WHERE id=?", [repo_id]
    ).fetchall()

    assert len(repos) == 1

    assert repos[0][0] == repo_url


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
        },
    }

    update_github_repo_perms(di, event, "any event")

    assert di.connection

    user_id = di.connection.execute(
        "SELECT uuid FROM users WHERE username='new_user'"
    ).fetchone()[0]

    update_github_repo_perms(di, event, "any event")

    new_user_id = di.connection.execute(
        "SELECT uuid FROM users WHERE username='new_user'"
    ).fetchone()[0]

    assert user_id == new_user_id

    rows = di.connection.execute("SELECT * FROM _user_repos").fetchall()

    assert len(rows) == 1


def test_invalid_events_are_ignored() -> None:
    di = TestDiContainer()
    di.reset()

    update_github_repo_perms(di, {}, "any event")
    update_github_repo_perms(di, {"sender": {}}, "any event")
    update_github_repo_perms(di, {"sender": {"type": "Robot"}}, "any event")
    update_github_repo_perms(di, {"sender": {"type": "User"}}, "any event")

    event = {
        "sender": {
            "type": "User",
            "login": "user A",
        },
        "repository": {
            "owner": {"login": "user B"},
        },
    }
    update_github_repo_perms(di, event, "any event")

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
        },
    }

    event_types = {
        "push": "write",
        "issues": "read",
    }

    for event_type, perm in event_types.items():
        update_github_repo_perms(di, event, event_type)

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
