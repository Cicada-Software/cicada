from pathlib import Path

from cicada.eval.find_files import find_ci_files


def test_find_ci_files() -> None:
    test_data = Path(__file__).parent / "test_data"

    files = list(find_ci_files(test_data))

    assert sorted(files) == [
        test_data / "a.ci",
        test_data / "b.c.ci",
        test_data / "folder" / "nested.ci",
    ]
