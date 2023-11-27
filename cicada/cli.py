import asyncio
import os
from argparse import ArgumentParser
from pathlib import Path
from typing import cast

from git import Repo

from cicada.domain.datetime import Datetime
from cicada.domain.triggers import CommitTrigger, GitSha
from cicada.eval.main import run_pipeline


def get_commit_trigger_for_current_git_repo() -> CommitTrigger:
    repo = Repo()
    current_commit = repo.head.commit
    origin = repo.remotes["origin"]

    return CommitTrigger(
        author=current_commit.author.name,
        repository_url=next(origin.urls),
        provider="github",
        message=str(current_commit.message),
        committed_on=cast(Datetime, current_commit.committed_datetime),
        sha=GitSha(current_commit.hexsha),
        ref=repo.head.ref.path,
        branch=repo.head.ref.name,
        default_branch=origin.refs["HEAD"].ref.remote_head,
    )


def main() -> None:
    parser = ArgumentParser(prog="cicada", description="Interpreter for the Cicada DSL")

    parser.add_argument("file")
    parser.add_argument("--env", "-e", nargs="*", metavar="KEY | KEY=VALUE", default=[])
    parser.add_argument("--secret", nargs="*", metavar="KEY=VALUE", default=[])

    args = parser.parse_args()

    file = Path(args.file)

    trigger = get_commit_trigger_for_current_git_repo()

    for env in args.env:
        k, v = parse_env_string(env)

        trigger.env[k] = v

    for secret in args.secret:
        k, v = parse_env_string(secret, use_env_default=False)

        trigger.secret[k] = v

    asyncio.run(run_pipeline(file.read_text(), str(file), trigger))


def parse_env_string(s: str, use_env_default: bool = True) -> tuple[str, str]:
    if "=" in s:
        k, v = s.split("=", maxsplit=1)

        return k, v

    if use_env_default:
        return s, os.getenv(s, "")

    raise ValueError("Secret must contain `=`")


if __name__ == "__main__":
    main()
