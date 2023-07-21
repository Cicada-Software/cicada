from dataclasses import is_dataclass
from enum import Enum
from typing import Any


def asjson(obj: Any) -> Any:  # type: ignore[misc]
    # TODO: this isnt JSON, rename function
    if isinstance(obj, dict):
        return {k: asjson(v) for k, v in obj.items()}

    if isinstance(obj, Enum):
        return obj.value

    if is_dataclass(obj):
        out: dict[str, Any] = {}  # type: ignore[misc]

        for name in dir(obj):
            attr = getattr(obj, name)

            if "__" in name or callable(attr):
                continue

            if attr is not None:
                out[name] = asjson(attr)

        return out

    if isinstance(obj, list):
        return [asjson(x) for x in obj]

    if isinstance(obj, int | float | str):
        return obj

    return str(obj)
