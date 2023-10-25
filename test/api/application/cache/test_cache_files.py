import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import ClassVar
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from cicada.application.cache.cache_files import CacheFilesForWorkflow, InvalidCacheObject
from cicada.domain.cache import CacheKey, CacheObject
from cicada.domain.session import WorkflowId


def test_cached_files_must_be_relative_to_passed_directory() -> None:
    cmd = CacheFilesForWorkflow(MagicMock())

    msg = "File `/` must be relative to current directory"

    with pytest.raises(InvalidCacheObject, match=re.escape(msg)):
        cmd.handle(
            files=[Path("/")],
            key=CacheKey("any key"),
            repository_url="example.com",
            workflow_id=WorkflowId(uuid4()),
            dir=Path("/some_dir"),
        )


def test_cached_files_must_exist() -> None:
    cmd = CacheFilesForWorkflow(MagicMock())

    msg = "File `/tmp/does_not_exist` does not exist"

    with pytest.raises(InvalidCacheObject, match=re.escape(msg)):
        cmd.handle(
            files=[Path("/tmp/does_not_exist")],
            key=CacheKey("any key"),
            repository_url="example.com",
            workflow_id=WorkflowId(uuid4()),
            dir=Path("/tmp/"),
        )


def test_cached_files_must_not_exceed_limit() -> None:
    class SmallCachedFiles(CacheFilesForWorkflow):
        MAX_CACHE_SIZE_IN_BYTES: ClassVar[int] = 100

    cmd = SmallCachedFiles(MagicMock())

    with NamedTemporaryFile(mode="w") as f:
        f.write("x" * (SmallCachedFiles.MAX_CACHE_SIZE_IN_BYTES + 1))
        f.flush()

        with pytest.raises(InvalidCacheObject, match="Cache is too big"):
            cmd.handle(
                files=[Path(f.name)],
                key=CacheKey("any key"),
                repository_url="example.com",
                workflow_id=WorkflowId(uuid4()),
                dir=Path("/tmp/"),
            )


def test_cached_files_are_archived_and_uploaded() -> None:
    cache_repo = MagicMock()

    cmd = CacheFilesForWorkflow(cache_repo)

    workflow_id = WorkflowId(uuid4())

    with NamedTemporaryFile(mode="w") as f:
        f.write("hello world")
        f.flush()

        cmd.handle(
            files=[Path(f.name)],
            key=CacheKey("abc123"),
            repository_url="example.com",
            workflow_id=workflow_id,
            dir=Path("/tmp/"),
        )

        cache_repo.store.assert_called()

        cache_object: CacheObject = cache_repo.store.call_args[0][0]

        assert cache_object.file.name.endswith(".tar.gz")
        assert cache_object.workflow_id == workflow_id
        assert cache_object.repository_url == "example.com"
        assert cache_object.key == CacheKey("abc123")
