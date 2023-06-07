import re
from pathlib import Path

import pytest

from cicada.tools.workflow_converter.github_actions import convert


def test_github_actions_workflow_convertion() -> None:
    """
    This will search for all files in the "data" folder, find all ".yaml"
    files, convert them, then compare the output to the file of the same name
    but with a ".ci" file extension instead.
    """

    for file in (Path(__file__).parent / "data").iterdir():
        if file.suffix == ".yaml":
            got = convert(file.read_text()).strip()

            expected = file.with_suffix(".ci").read_text().strip()

            assert expected == got


def test_branch_globs_not_allowed() -> None:
    # See: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#filter-pattern-cheat-sheet

    disallowed_globs = (
        # star glob (0 or more non `/` characters)
        "*abc",
        "abc*",
        "abc*xyz",
        # double star glob (0 or more characters)
        "**abc",
        "abc**",
        "abc**xyz",
        # repeat globs
        "abc?",
        "abc+",
        # charset glob
        "[abc]xyz",
        # negation glob
        "!abc",
    )

    workflow = """\
on:
  push:
    branches:
      - "{}"
"""

    for glob in disallowed_globs:
        msg = re.escape(f"Branch glob `{glob}` not supported yet")

        with pytest.raises(AssertionError, match=msg):
            convert(workflow.format(glob))
