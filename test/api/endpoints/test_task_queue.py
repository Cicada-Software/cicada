from asyncio import create_task, sleep

from cicada.api.endpoints.task_queue import TaskQueue


async def test_task_queue_adds_tasks() -> None:
    q = TaskQueue()

    async def f() -> None:
        pass

    q.add(create_task(f()))
    q.add(create_task(f()))
    q.add(create_task(f()))

    await sleep(0.01)

    assert not len(q)


async def test_cancelled_task_is_removed() -> None:
    q = TaskQueue()

    async def f() -> None:
        await sleep(9999)

    task = create_task(f())
    q.add(task)

    assert len(q) == 1

    task.cancel()

    await sleep(0.01)
    assert not len(q)


async def test_coroutine_can_be_added_directly() -> None:
    q = TaskQueue()

    did_run = False

    async def f() -> None:
        nonlocal did_run

        did_run = True

    q.add(f())

    await sleep(0.01)

    assert did_run


async def test_truthy_and_falsey_queue() -> None:
    q = TaskQueue()

    assert not q
    assert not len(q)

    async def f() -> None:
        await sleep(9999)

    task = create_task(f())
    q.add(task)

    assert q
    assert len(q) == 1

    task.cancel()
