from collections.abc import Generator, Iterator
from typing import Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V")


class GeneratorWrapper(Generic[T, U, V]):
    """
    This is a simple wrapper object which takes in a generator, allows you to
    iterate over it, while still being able to get the resulting value returned
    by the generator. In most cases you only care about the yielded value, but
    in cases where you need to get the final value from a generator in a for
    loop, you don't have any good options. This wrapper fixes that.
    """

    value: V | None

    def __init__(self, generator: Generator[T, U, V]) -> None:
        self.generator = generator
        self.value = None

    def __iter__(self) -> Iterator[T]:
        self.value = yield from self.generator
