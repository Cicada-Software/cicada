import tarfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory, mkstemp
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cicada.application.cache.restore_cache import RestoreCache
from cicada.domain.cache import CacheKey, CacheObject, CacheObjectId
from cicada.domain.repo.cache_repo import ICacheRepo
from cicada.domain.session import Session
from test.common import build


def test_unknown_cache_key_returns_false() -> None:
    cache_repo = MagicMock()
    cache_repo.get.return_value = None

    cmd = RestoreCache(cache_repo)

    output = cmd.handle(
        repository_url="anything",
        key="anything",
        extract_to=Path("/tmp"),
    )

    assert not output


class TempCacheRepo(ICacheRepo):
    cache_object: CacheObject | None = None

    def store(self, cache: CacheObject) -> None:
        self.cache_object = cache

    def get(self, repository_url: str, key: str) -> CacheObject | None:
        return self.cache_object

    def key_exists(self, repository_url: str, key: str) -> bool:
        return True


@contextmanager
def create_cache_object(files: list[Path], dir: Path | None = None) -> Iterator[CacheObject]:
    session = build(Session)

    tarfile_name = Path(mkstemp(suffix=".tar.gz")[1])

    with open(tarfile_name, "w+b") as f:
        with tarfile.open(fileobj=f, mode="w:gz") as tf:
            for file in files:
                if dir:
                    tf.add(file, arcname=str(file.relative_to(dir)))
                else:
                    tf.add(file)

        f.flush()

        cache_object = CacheObject(
            id=CacheObjectId(uuid4()),
            repository_url=session.trigger.repository_url,
            key=CacheKey("any key"),
            session_id=session.id,
            session_run=session.run,
            file=Path(f.name),
        )

        yield cache_object

    if tarfile_name.exists():
        tarfile_name.unlink()


def test_cannot_restore_caches_with_symlinks_outside_cache_dir() -> None:
    link = Path("/tmp/cicada-link-test")
    link.symlink_to("/bin")

    try:
        with create_cache_object(files=[link]) as cache:
            cache_repo = MagicMock()
            cache_repo.get.return_value = cache

            cmd = RestoreCache(cache_repo)

            msg = "Symlink cannot resolve to outside cache"

            with pytest.raises(ValueError, match=msg):
                cmd.handle("any repo", "any key", Path("/tmp"))

        assert not cache.file.exists()

    finally:
        link.unlink()


def test_files_extracted_successfully() -> None:
    with (
        TemporaryDirectory() as temp_dir,
        NamedTemporaryFile() as temp_file,
    ):
        extract_to_dir = Path(temp_dir)

        cache_file = Path(temp_file.name)
        cache_file.write_text("Hello world!")

        with create_cache_object(
            files=[cache_file],
            dir=Path("/tmp"),
        ) as cache:
            cache_repo = MagicMock()
            cache_repo.get.return_value = cache

            cmd = RestoreCache(cache_repo)
            cmd.handle("any repo", "any key", extract_to_dir)

            files = list(extract_to_dir.iterdir())
            assert len(files) == 1

            assert files[0].name == cache_file.name
            assert files[0].read_text() == "Hello world!"

    assert not cache.file.exists()
