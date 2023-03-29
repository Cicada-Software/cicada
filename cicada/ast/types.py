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
        raise NotImplementedError()


class UnknownType(Type):
    """
    A type which is not yet known. Used in the early stages of AST generation.
    """

    def __str__(self) -> str:
        return "<unknown>"


class UnitType(Type):
    """
    Represents an "empty" result, basically "void" in C-style languages.
    """

    def __str__(self) -> str:
        return "()"


class UnreachableType(Type):
    """
    Represents a type that cannot exist, or is a result of some run time error.
    """

    def __str__(self) -> str:
        return "<unreachable>"


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
class RecordField:
    name: str
    type: Type


@dataclass
class RecordType(Type):
    """
    A record is essentially a named tuple. They are immutable, have fields,
    where each field can have whatever type it wants. The structure of a record
    cannot change once created though.
    """

    # TODO: turn fields into a dict
    fields: list[RecordField] = field(default_factory=list)

    def __str__(self) -> str:
        # TODO: return more descriptive string type
        return "record"
