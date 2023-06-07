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


def is_supported_glob(glob: str) -> bool:
    return not set(glob).intersection("*?+[]!")


def convert_push_event(push: dict[str, Any] | str) -> str:  # type: ignore
    event_type = "git.push"
    condition: None | str = None

    if isinstance(push, dict) and (branches := push.get("branches")):
        assert isinstance(branches, list), "expected `branches` to be a list"

        # Remove "**" globs because they match everything, meaning there is no
        # need to create a condition for them.
        branches = [b for b in branches if b != "**"]

        for branch in branches:
            if not is_supported_glob(branch):
                raise AssertionError(
                    f"Branch glob `{branch}` not supported yet"
                )

        if branches:
            condition = " or ".join(f'event.branch is "{b}"' for b in branches)

    line = f"on {event_type}"

    if condition:
        line += f" where {condition}"

    return f"{line}\n"


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
                if line.split()[0] in SHELL_ALIASES:
                    commands += f"{line}\n"
                else:
                    commands += f"shell {line}\n"

            commands += "\n"

    return commands


def convert_jobs(jobs: dict[str, Any]) -> str:  # type: ignore
    workflow = ""

    assert isinstance(jobs, dict), "`jobs` field must be dict"
    assert len(jobs) == 1, "Cannot have multiple `jobs` fields"

    job_name, job = list(jobs.items())[0]

    assert isinstance(job, dict), f"Expected `{job_name}` to be a dict"

    if runs_on := job.get("runs-on", None):
        image = WORKFLOW_IMAGE_MAPPINGS.get(runs_on)

        if image is None:
            raise AssertionError(f"Unexpected runner `{runs_on}`")

        workflow += f"runs_on image {image}\n\n"

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

    if on := data.get("on"):
        assert isinstance(on, dict | list)

        workflow += convert_on(on)

    if jobs := data.get("jobs"):
        workflow += convert_jobs(jobs)

    return workflow.strip()
