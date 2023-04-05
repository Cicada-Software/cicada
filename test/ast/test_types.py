import pytest

from cicada.ast.types import BooleanType, NumericType, StringType, UnionType


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
