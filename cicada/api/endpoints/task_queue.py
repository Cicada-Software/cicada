from asyncio import Task, create_task
from collections.abc import Coroutine
from typing import Any


class TaskQueue:
    """
    Wrapper class for queueing async background tasks. This task will hold onto
    the lifetime of the object, and once the task finishes it is discarded.
    """

    tasks: set[Task[None]]

    def __init__(self) -> None:
        self.tasks = set()

    def add(  # type: ignore[misc]
        self,
        task: Task[None] | Coroutine[Any, Any, None],
    ) -> None:
        if not isinstance(task, Task):
            task = create_task(task)

        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def __len__(self) -> int:
        return len(self.tasks)
