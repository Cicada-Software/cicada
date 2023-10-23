import re
import shlex
from typing import Any

from ruamel.yaml import YAML

from cicada.ast.generate import SHELL_ALIASES

# Note that the images GitHub provides will include lots of common software,
# but the ones we are using are just the plain ubuntu docker images, meaning
# you will have to install everything you need yourself. There is a fine line
# between "including what people need" vs "including everything, bloating the
# image size, and wasting a lot of resources", something that Cicada will have
# to address at some point in the future.
WORKFLOW_IMAGE_MAPPINGS = {
    "ubuntu-latest": "ubuntu:22.04",
    "ubuntu-22.04": "ubuntu:22.04",
    "ubuntu-20.04": "ubuntu:20.04",
}

GITHUB_ISSUE_TYPE_MAPPINGS = {
    "opened": "open",
    "closed": "close",
}


# TODO: use same regex as identifiers
ENV_VAR_REGEX = re.compile("[A-Za-z_][A-Za-z0-9_]+")
GITHUB_EXPR = re.compile(r"^\$\{\{(.*)\}\}$")


def is_supported_glob(glob: str) -> bool:
    if not set(glob).intersection("*?+[]!"):
        return True

    star_count = glob.count("*")

    if (glob.startswith("**") or glob.endswith("**")) and star_count == 2:
        return True

    return False


def convert_name(title: str) -> str:
    assert isinstance(title, str)
    return f"title {title}\n\n"


def convert_push_event(push: dict[str, Any] | str) -> str:  # type: ignore
    event_type = "git.push"
    conditions: list[str] = []

    if isinstance(push, dict) and (branches := push.get("branches")):
        assert isinstance(branches, list), "expected `branches` to be a list"

        # Remove "**" globs because they match everything, meaning there is no
        # need to create a condition for them.
        branches = [b for b in branches if b != "**"]

        for branch in branches:
            if not is_supported_glob(branch):
                raise AssertionError(f"Branch glob `{branch}` not supported yet")

            if branch.startswith("**"):
                conditions.append(f'event.branch.ends_with("{branch[2:]}")')
            elif branch.endswith("**"):
                conditions.append(f'event.branch.starts_with("{branch[:-2]}")')
            else:
                conditions.append(f'event.branch is "{branch}"')

    line = f"on {event_type}"

    if conditions:
        line += f" where {' or '.join(conditions)}"

    return f"{line}\n"


def convert_issues_event(issues: dict[str, Any]) -> str:  # type: ignore
    types = issues.get("types")

    assert isinstance(types, list), "expected list of `types`"
    assert len(types) == 1, "only one issue type can be specified"

    issue_type = GITHUB_ISSUE_TYPE_MAPPINGS.get(types[0])

    assert issue_type, "only opened/closed issues are supported currently"

    return f"on issue.{issue_type}\n"


def convert_github_expr(expr: str) -> tuple[str, bool]:
    """
    Convert a GitHub expression in the form ${{ expr }} into a Cicada expr.

    This function returns 2 values: One contains the resulting expression, and
    the other is a boolean indicating whether the returned expression is a
    Cicada expression: If no expression is detected or it cannot be converted,
    the original expr is returned.
    """

    if match := GITHUB_EXPR.match(expr.strip('"')):
        return f"({match.group(1).strip()})", True

    return expr, False


def convert_steps(steps: list[Any]) -> str:  # type: ignore
    commands = ""

    for i, step in enumerate(steps):
        assert isinstance(step, dict), f"expected step {i} to be a dict"

        # These are importable GitHub actions which Cicada is not capable
        # of using. There are certain actions such as the checkout actions
        # which we could support in the future, but since Cicada offers
        # no way to tune how the git clone process works there is no need.
        if uses := step.get("uses"):
            # Cicada will auto checkout the repository by default, so this
            # action can be ignored safely.
            if uses.startswith("actions/checkout"):
                continue

            commands += f"# ERR: GitHub Action `{uses}` not supported\n\n"

            continue

        if name := step.get("name"):
            commands += f"# {name}\n"

        if cmd := step.get("run"):
            cmd = cmd.strip()

            for line in cmd.split("\n"):
                exprs = [convert_github_expr(x) for x in shlex.split(line)]

                parts = [expr if is_safe else shlex.quote(expr) for expr, is_safe in exprs]

                cmd = " ".join(parts)

                if parts[0] in SHELL_ALIASES:
                    commands += f"{cmd}\n"
                else:
                    commands += f"shell {cmd}\n"

            commands += "\n"

    return commands


def convert_env_vars(env: dict[str, str]) -> str:
    assert isinstance(env, dict), "`env` must be a dict"

    output = ""

    for k, v in env.items():
        assert ENV_VAR_REGEX.match(k), f"Invalid variable name `{k}`"

        v = str(v).replace('"', '\\"')

        output += f'env.{k} = "{v}"\n'

    return f"{output}\n"


def convert_jobs(jobs: dict[str, Any]) -> str:  # type: ignore
    workflow = ""

    assert isinstance(jobs, dict), "`jobs` field must be dict"
    assert len(jobs) == 1, "Cannot have multiple `jobs` fields"

    job_name, job = next(iter(jobs.items()))

    assert isinstance(job, dict), f"Expected `{job_name}` to be a dict"

    if runs_on := job.get("runs-on", None):
        image = WORKFLOW_IMAGE_MAPPINGS.get(runs_on)

        if image is None:
            raise AssertionError(f"Unexpected runner `{runs_on}`")

        workflow += f"run_on image {image}\n\n"

    if env := job.get("env"):
        workflow += convert_env_vars(env)

    if steps := job.get("steps"):
        assert isinstance(steps, list), "`steps` must be a list"

        workflow += convert_steps(steps)

    return workflow


def convert_on(on: dict[str, Any] | list[Any]) -> str:  # type: ignore
    events = ""

    if "push" in on:
        if isinstance(on, dict):
            events += convert_push_event(on.pop("push"))
        else:
            on.remove("push")
            events += convert_push_event("push")

    elif "issues" in on:
        assert isinstance(on, dict), "Only opened and closed issues are supported"

        events += convert_issues_event(on.pop("issues"))

    for event in on:
        events += f"# ERR: `{event}` events are currently unsupported\n"

    return f"{events}\n"


def convert(contents: str) -> str:
    """
    Convert the contents of a GitHub Actions YAML workflow file to a Cicada
    workflow file. This API is subject to change, and is very be error prone.
    """

    data = YAML(typ="safe").load(contents)

    workflow = ""

    if name := data.get("name"):
        workflow += convert_name(name)

    if on := data.get("on"):
        assert isinstance(on, dict | list | str)

        if isinstance(on, str):
            on = [on]

        workflow += convert_on(on)

    if env := data.get("env"):
        workflow += convert_env_vars(env)

    if jobs := data.get("jobs"):
        workflow += convert_jobs(jobs)

    return workflow.strip()


if __name__ == "__main__":  # pragma: no cover
    import sys
    from pathlib import Path

    for filename in sys.argv[1:]:
        file = Path(filename)

        ci = convert(file.read_text())
        file.with_suffix(".ci").write_text(ci)
