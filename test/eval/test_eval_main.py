from unittest.mock import MagicMock, patch

from cicada.eval.main import run_pipeline
from test.ast.common import build_trigger


def test_workflow_ignored_if_trigger_type_doesnt_match() -> None:
    code = """\
on issue.open

echo this should not run
"""

    trigger = build_trigger("git.push")

    m = MagicMock()

    with (
        patch("subprocess.run", return_value=m) as p,
        patch.object(m, "returncode", 0),
    ):
        run_pipeline(code, trigger=trigger)

    p.assert_not_called()
