import logging
import tarfile
from pathlib import Path

from cicada.domain.repo.cache_repo import ICacheRepo


class RestoreCache:
    def __init__(self, cache_repo: ICacheRepo) -> None:
        self.cache_repo = cache_repo

        self.logger = logging.getLogger("cicada")

    def handle(self, repository_url: str, key: str, extract_to: Path) -> bool:
        cache_object = self.cache_repo.get(repository_url, key)

        if not cache_object:
            return False

        try:
            # TODO: switch to Python 3.11.4 extraction filters
            with tarfile.open(cache_object.file, mode="r:*") as tf:
                for member in tf.getmembers():
                    if member.isblk() or member.ischr() or member.isfifo():
                        raise ValueError("Cannot extract special files")

                    if member.islnk() or member.issym():
                        linked_to = tf.getmember(member.name)

                        if linked_to.isdir():
                            link_path = Path(member.name, member.linkname)
                        else:
                            link_path = Path(member.name).parent / member.linkname

                        if not link_path.resolve().is_relative_to(Path.cwd()):
                            raise ValueError("Symlink cannot resolve to outside cache")

                tf.extractall(extract_to)  # noqa: S202

        finally:
            cache_object.file.unlink()

        return True
