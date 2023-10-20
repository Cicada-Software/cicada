import pytest

from cicada.ast.types import (
    BooleanType,
    FunctionType,
    ListType,
    NumericType,
    StringType,
    UnionType,
    UnitType,
    VariadicTypeArg,
)


def test_non_unique_fields_removed() -> None:
    union = UnionType((BooleanType(), NumericType(), NumericType()))

    assert union == UnionType((BooleanType(), NumericType()))


def test_flipped_types_still_match() -> None:
    lhs = UnionType((BooleanType(), NumericType()))
    rhs = UnionType((NumericType(), BooleanType()))

    assert lhs == rhs


def test_longer_union_types_are_not_equal() -> None:
    lhs = UnionType((BooleanType(), NumericType()))
    rhs = UnionType((BooleanType(), NumericType(), StringType()))

    assert lhs != rhs


def test_disjoint_unions_are_not_equal() -> None:
    lhs = UnionType((BooleanType(), NumericType()))
    rhs = UnionType((BooleanType(), StringType()))

    assert lhs != rhs


def test_single_type_unions_throw_error() -> None:
    with pytest.raises(ValueError, match="Union must have 2 or more types"):
        UnionType((NumericType(),))

    with pytest.raises(ValueError, match="Union must have 2 or more types"):
        UnionType(())


def test_stringify_union_type() -> None:
    assert str(UnionType((BooleanType(), NumericType()))) == "bool | number"


def test_stringify_variadic_type() -> None:
    assert str(VariadicTypeArg(StringType())) == "string"


def test_stringify_function_type() -> None:
    ty = FunctionType([StringType()], rtype=UnitType())
    expected = "(string) -> ()"

    assert str(ty) == expected


def test_create_list_type() -> None:
    ty = ListType(NumericType())

    assert ty.inner_type == NumericType()
    assert ty == ListType(NumericType())

    assert str(ty) == "[number]"
