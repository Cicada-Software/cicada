import re
from dataclasses import dataclass, field
from typing import ClassVar

from cicada.domain.datetime import UtcDatetime


@dataclass(frozen=True)
class Secret:
    key: str
    value: str
    updated_at: UtcDatetime = field(default_factory=UtcDatetime.now)

    MAX_KEY_LEN: ClassVar[int] = 256
    KEY_REGEX: ClassVar[re.Pattern[str]] = re.compile("^[A-Za-z_][A-Za-z0-9_]*$")

    # 1MB might be too small, though this should be good for now
    MAX_VALUE_LEN: ClassVar[int] = 1024

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("Key cannot be empty")

        if len(self.key) > self.MAX_KEY_LEN:
            raise ValueError(f"Key is too long (max {self.MAX_KEY_LEN} chars)")

        if not self.KEY_REGEX.match(self.key):
            raise ValueError(f"Key does not match regex: {self.KEY_REGEX.pattern}")

        if len(self.value) > self.MAX_VALUE_LEN:
            raise ValueError(f"Value is too long (max {self.MAX_VALUE_LEN} chars)")
