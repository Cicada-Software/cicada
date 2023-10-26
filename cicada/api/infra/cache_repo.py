import logging
import os
import sqlite3
from pathlib import Path
from tempfile import mkstemp
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from uuid import UUID

import boto3

from cicada.api.infra.db_connection import DbConnection
from cicada.api.settings import S3CacheSettings
from cicada.domain.cache import CacheKey, CacheObject, CacheObjectId
from cicada.domain.datetime import UtcDatetime
from cicada.domain.repo.cache_repo import ICacheRepo
from cicada.domain.session import WorkflowId

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client


class CacheRepo(ICacheRepo, DbConnection):
    def store(self, cache: CacheObject) -> None:
        workflow_id = self.conn.execute(
            "SELECT id FROM workflows WHERE uuid=?;", [cache.workflow_id]
        ).fetchone()[0]

        assert workflow_id

        self.conn.execute(
            """
            INSERT INTO cache_objects (
                uuid,
                repository_url,
                key,
                workflow_id,
                created_at
            ) VALUES (?, ?, ?, ?, ?);
            """,
            [
                cache.id,
                cache.repository_url,
                str(cache.key),
                workflow_id,
                cache.created_at,
            ],
        )
        self.conn.commit()

        settings = S3CacheSettings()

        s3 = self._get_s3_client()

        s3.upload_file(
            Filename=str(cache.file),
            Bucket=settings.bucket,
            Key=self._generate_full_key_name(cache),
        )

    def get(self, repository_url: str, key: str) -> CacheObject | None:
        """
        Return a cache object for the given repository URL and key if one
        exists, otherwise return None.

        Note: The caller is responsible for deleting/cleaning up the file
        returned via the `file` field of the cache object.
        """

        row = self._get_cache_object_from_key(repository_url, key)

        if row is None:
            return None

        url = urlparse(repository_url)

        # TODO: store extension in DB
        extension = ".tar.gz"

        filename = mkstemp(suffix=extension)[1]

        try:
            settings = S3CacheSettings()

            s3 = self._get_s3_client()

            s3.download_file(
                Filename=filename,
                Bucket=settings.bucket,
                Key=f"caches/{url.netloc}{url.path}/{key}{extension}",
            )

            return CacheObject(
                id=CacheObjectId(UUID(row["uuid"])),
                repository_url=row["repository_url"],
                key=CacheKey(row["key"]),
                workflow_id=WorkflowId(UUID(row["workflow_uuid"])),
                file=Path(filename),
                created_at=UtcDatetime.fromisoformat(row["created_at"]),
            )

        except Exception:  # noqa: BLE001
            logging.getLogger("cicada").exception("Could not download cache")

            os.remove(filename)

            return None

    def key_exists(self, repository_url: str, key: str) -> bool:
        return bool(self._get_cache_object_from_key(repository_url, key))

    @staticmethod
    def _generate_full_key_name(cache: CacheObject) -> str:
        url = urlparse(cache.repository_url)

        extension = "".join(cache.file.suffixes)

        return f"caches/{url.netloc}{url.path}/{cache.key}{extension}"

    @staticmethod
    def _get_s3_client() -> "S3Client":
        settings = S3CacheSettings()

        return boto3.client(
            "s3",
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key,
            endpoint_url=settings.url,
        )

    def _get_cache_object_from_key(
        self,
        repository_url: str,
        key: str,
    ) -> sqlite3.Row | None:
        return self.conn.execute(  # type: ignore
            """
            SELECT
                c.uuid AS uuid,
                repository_url,
                key,
                w.uuid AS workflow_uuid,
                created_at
            FROM cache_objects c
            JOIN workflows w ON w.id = c.workflow_id
            WHERE c.repository_url=? and c.key=?
            ORDER BY created_at DESC
            LIMIT 1;
            """,
            [repository_url, key],
        ).fetchone()
