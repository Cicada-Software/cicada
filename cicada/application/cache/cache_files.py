import logging
import tarfile
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import ClassVar
from uuid import uuid4

from cicada.application.exceptions import InvalidRequest
from cicada.domain.cache import CacheKey, CacheObject, CacheObjectId
from cicada.domain.repo.cache_repo import ICacheRepo
from cicada.domain.session import WorkflowId


class InvalidCacheObject(InvalidRequest):
    def __init__(self, msg: str) -> None:
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


class CacheFilesForWorkflow:
    MAX_CACHE_SIZE_IN_BYTES: ClassVar[int] = 250 * 1000 * 1000  # 250MB

    def __init__(self, cache_repo: ICacheRepo) -> None:
        self.cache_repo = cache_repo

        self.logger = logging.getLogger("cicada")

    def handle(
        self,
        files: list[Path],
        key: CacheKey,
        repository_url: str,
        workflow_id: WorkflowId,
        dir: Path,
    ) -> None:
        size = 0

        with NamedTemporaryFile(mode="w+b", suffix=".tar.gz") as f:
            with tarfile.open(fileobj=f, mode="w:gz") as tf:
                for file in files:
                    file = (dir / file).resolve()

                    if not file.is_relative_to(dir):
                        raise InvalidCacheObject(
                            f"File `{file}` must be relative to current directory"
                        )

                    if not file.exists():
                        raise InvalidCacheObject(f"File `{file}` does not exist")

                    size += file.stat().st_size

                    if size > self.MAX_CACHE_SIZE_IN_BYTES:
                        size_in_mb = int(self.MAX_CACHE_SIZE_IN_BYTES / 1_000 * 1_000)

                        raise InvalidCacheObject(
                            f"Cache is too big (must be less than {size_in_mb}MB)"
                        )

                    tf.add(file, arcname=str(file.relative_to(dir)))

            f.flush()

            cache_object = CacheObject(
                id=CacheObjectId(uuid4()),
                repository_url=repository_url,
                key=key,
                workflow_id=workflow_id,
                file=Path(f.name),
            )

            self.logger.debug(f"Uploading cache id {cache_object.id}")

            start = time.time()
            self.cache_repo.store(cache_object)
            elapsed = time.time() - start

            self.logger.debug(f"Upload took {elapsed} seconds")
