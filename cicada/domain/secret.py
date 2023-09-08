from dataclasses import dataclass, field

from cicada.domain.datetime import UtcDatetime


@dataclass
class Secret:
    key: str
    value: str
    updated_at: UtcDatetime = field(default_factory=UtcDatetime.now)
