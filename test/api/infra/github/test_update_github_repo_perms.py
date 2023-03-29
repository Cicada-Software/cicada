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

    update_github_repo_perms(di, event)

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

    update_github_repo_perms(di, event)

    assert di.connection

    user_id = di.connection.execute(
        "SELECT uuid FROM users WHERE username='new_user'"
    ).fetchone()[0]

    update_github_repo_perms(di, event)

    new_user_id = di.connection.execute(
        "SELECT uuid FROM users WHERE username='new_user'"
    ).fetchone()[0]

    assert user_id == new_user_id

    rows = di.connection.execute("SELECT * FROM _user_repos").fetchall()

    assert len(rows) == 1


def test_invalid_events_are_ignored() -> None:
    di = TestDiContainer()
    di.reset()

    update_github_repo_perms(di, {})
    update_github_repo_perms(di, {"sender": {}})
    update_github_repo_perms(di, {"sender": {"type": "Robot"}})
    update_github_repo_perms(di, {"sender": {"type": "User"}})

    event = {
        "sender": {
            "type": "User",
            "login": "user A",
        },
        "repository": {
            "owner": {"login": "user B"},
        },
    }
    update_github_repo_perms(di, event)

    assert di.connection
    rows = di.connection.execute("SELECT * FROM _user_repos").fetchall()

    assert not rows
