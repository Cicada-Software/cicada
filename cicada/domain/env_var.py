from dataclasses import dataclass


@dataclass
class EnvironmentVariable:
    key: str
    value: str
