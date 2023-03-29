from collections.abc import Generator
from pathlib import Path

FOLDER_BAN_LIST = {
    ".venv",
    "node_modules",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}


def find_ci_files(start: Path) -> Generator[Path, None, None]:
    for path in start.iterdir():
        if path.suffix == ".ci":
            yield path

        if path.is_dir() and path.name not in FOLDER_BAN_LIST:
            yield from find_ci_files(path)
