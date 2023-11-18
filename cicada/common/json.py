from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def asjson(obj: Any) -> Any:  # type: ignore[misc]
    # TODO: this isnt JSON, rename function
    if obj is None:
        return None

    if isinstance(obj, dict):
        return {str(asjson(k)): asjson(v) for k, v in obj.items()}

    if isinstance(obj, Enum):
        return obj.value

    if is_dataclass(obj):
        out: dict[str, Any] = {}  # type: ignore[misc]

        for name in dir(obj):
            attr = getattr(obj, name)

            if "__" in name or callable(attr):
                continue

            out[name] = asjson(attr)

        return out

    if isinstance(obj, list):
        return [asjson(x) for x in obj]

    if isinstance(obj, int | float | str):
        return obj

    if isinstance(obj, Path):
        return "" if obj == Path() else str(obj)

    return str(obj)
