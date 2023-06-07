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


def convert(contents: str) -> str:
    """
    Convert the contents of a GitHub Actions YAML workflow file to a Cicada
    workflow file. This API is subject to change, and is very be error prone.
    """

    data = YAML(typ="safe").load(contents)

    workflow = ""

    if on := data.get("on"):
        if push := on.get("push"):
            event_type = "git.push"
            condition: None | str = None

            if branches := push.get("branches"):
                for branch in branches:
                    assert (
                        "*" not in branch
                    ), f"Regex branch `{branch}` not supported yet"

                condition = " or ".join(
                    f'event.branch is "{b}"' for b in branches
                )

            line = f"on {event_type}"

            if condition:
                line += f" where {condition}"

            workflow += f"{line}\n\n"

    if jobs := data.get("jobs"):
        assert isinstance(jobs, dict), "`jobs` field must be dict"
        assert len(jobs) == 1, "Cannot have multiple `jobs` fields"

        job_name, job = list(jobs.items())[0]

        assert isinstance(job, dict), f"Expected `{job_name}` to be a dict"

        runs_on = job.get("runs-on", None)

        if runs_on is not None:
            image = WORKFLOW_IMAGE_MAPPINGS.get(runs_on)

            if image is None:
                raise AssertionError(f"Unexpected runner `{runs_on}`")

            workflow += f"runs_on image {image}\n\n"

        if steps := job.get("steps"):
            assert isinstance(steps, list), "`steps` must be a list"

            for i, step in enumerate(steps):
                assert isinstance(
                    step, dict
                ), f"expected step {i} to be a dict"

                # These are importable GitHub actions which Cicada is not capable
                # of using. There are certain actions such as the checkout actions
                # which we could support in the future, but since Cicada offers
                # no way to tune how the git clone process works there is no need.
                if "uses" in step:
                    continue

                if name := step.get("name"):
                    workflow += f"# {name}\n"

                if cmd := step.get("run"):
                    if cmd.split()[0] in SHELL_ALIASES:
                        workflow += f"{cmd}\n\n"
                    else:
                        workflow += f"shell {cmd}\n\n"

    return workflow.strip()
