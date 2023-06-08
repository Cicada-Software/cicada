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

CICADA_IGNORE_FILE = ".cicadaignore"


def find_ci_files(dir: Path) -> Generator[Path, None, None]:
    if (dir / CICADA_IGNORE_FILE).exists():
        return

    for path in dir.iterdir():
        if path.suffix == ".ci":
            yield path

        if path.is_dir() and path.name not in FOLDER_BAN_LIST:
            yield from find_ci_files(path)
