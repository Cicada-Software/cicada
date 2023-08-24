from dataclasses import dataclass


@dataclass
class Secret:
    key: str
    value: str
