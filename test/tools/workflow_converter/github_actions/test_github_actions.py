from pathlib import Path

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
