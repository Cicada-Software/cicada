from collections.abc import Sequence
from dataclasses import dataclass, field


class Type:
    """
    Abstract class for representing type information.

    Each type should declare a `__str__` method which will define the pretty
    printable version of the type.
    """

    def __eq__(self, other: object) -> bool:
        return type(self) == type(other)

    def __str__(self) -> str:
        raise NotImplementedError


class UnknownType(Type):
    """
    A type which is not yet known. Used in the early stages of AST generation.
    """

    def __str__(self) -> str:
        return "<unknown>"  # pragma: no cover


class UnitType(Type):
    """
    Represents an "empty" result, basically "void" in C-style languages.
    """

    def __str__(self) -> str:
        return "()"  # pragma: no cover


class UnreachableType(Type):
    """
    Represents a type that cannot exist, or is a result of some run time error.
    """

    def __str__(self) -> str:
        return "<unreachable>"  # pragma: no cover


class NumericType(Type):
    def __str__(self) -> str:
        return "number"


class StringType(Type):
    def __str__(self) -> str:
        return "string"


class BooleanType(Type):
    def __str__(self) -> str:
        return "bool"


@dataclass
class RecordType(Type):
    """
    A record is essentially a named tuple. They are immutable, have fields,
    where each field can have whatever type it wants. The structure of a record
    cannot change once created though.
    """

    fields: dict[str, Type] = field(default_factory=dict)

    def __str__(self) -> str:
        # TODO: return more descriptive string type
        return "record"


# TODO: make this frozen
@dataclass
class CommandType(RecordType):
    fields: dict[str, Type] = field(
        default_factory=lambda: {
            "exit_code": NumericType(),
            "stdout": StringType(),
            # TODO: add runtime duration
        }
    )


@dataclass
class ModuleType(RecordType):
    name: str = field(kw_only=True)


BOOL_LIKE_TYPES = (BooleanType(), NumericType(), StringType())


class UnionType(Type):
    """
    A union type is a type which can be one of 2 or more types. A value with a
    union type will need to be type checked in order to make sure it is of the
    desired types.
    """

    types: tuple[Type, ...]

    __match_args__ = ("types",)

    def __init__(self, types: Sequence[Type]) -> None:
        copy: list[Type] = []

        # Copy unique types while maintaining order
        for ty in types:
            if ty not in copy:
                copy.append(ty)

        self.types = tuple(copy)

        if len(self.types) < 2:
            raise ValueError("Union must have 2 or more types")

    @classmethod
    def union_or_single(cls, types: Sequence[Type]) -> Type:
        assert types

        try:
            return cls(types)

        except ValueError:
            return types[0]

    def __eq__(self, o: object) -> bool:
        if not (isinstance(o, UnionType) and len(o.types) == len(self.types)):
            return False

        copy = list(o.types)

        for lhs in self.types:
            for i, rhs in enumerate(copy):
                if lhs == rhs:
                    copy.pop(i)
                    break
            else:
                return False
        return True

    def __str__(self) -> str:
        return " | ".join(str(ty) for ty in self.types)


class VariadicTypeArg(Type):
    """
    A wrapper that expresses a repeatable variadic type. For example, a
    function that takes 0-N string types should use a variadic argument type to
    express this.
    """

    type: Type

    __match_args__ = ("type",)

    def __init__(self, type: Type) -> None:
        self.type = type

    def __eq__(self, other: object) -> bool:
        return isinstance(other, VariadicTypeArg) and other.type == self.type

    def __str__(self) -> str:
        return str(self.type)


class FunctionType(Type):
    """
    A function type is used to represent the arguments/return types of a
    function definition or function call.
    """

    arg_types: list[Type]
    rtype: Type

    __match_args__ = ("arg_types", "rtype")

    def __init__(
        self,
        arg_types: list[Type],
        rtype: Type,
    ) -> None:
        self.arg_types = arg_types
        self.rtype = rtype

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, FunctionType)
            and other.arg_types == self.arg_types
            and other.rtype == self.rtype
        )

    def __str__(self) -> str:
        args = ", ".join(str(ty) for ty in self.arg_types)

        return f"({args}) -> {self.rtype}"


class ListType(Type):
    """
    List types are similar to Python list types in that they can only contain
    one type. This type is allowed to be unknown, for example, when creating an
    empty list without a type annotation.
    """

    inner_type: Type

    __match_args__ = ("inner_type",)

    def __init__(self, inner_type: Type) -> None:
        self.inner_type = inner_type

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ListType) and other.inner_type == self.inner_type

    def __str__(self) -> str:
        return f"[{self.inner_type}]"


TYPE_NAMES = {
    "string": StringType,
    "number": NumericType,
    "bool": BooleanType,
    "()": UnitType,
}


def string_to_type(s: str) -> Type | None:
    if ty := TYPE_NAMES.get(s):
        return ty()

    return None
