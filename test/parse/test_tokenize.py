import pytest

from cicada.common.generator_wrapper import GeneratorWrapper
from cicada.parse.token import (
    BooleanLiteralToken,
    IdentifierToken,
    NewlineToken,
    WhiteSpaceToken,
)
from cicada.parse.tokenize import (
    KEYWORD_NAMES,
    TOKEN_SEPARATORS,
    Chunk,
    FloatLiteralToken,
    IntegerLiteralToken,
    StringLiteralToken,
    Token,
    chunk_stream,
    group_chunks,
    tokenize,
)


def test_chunk_simple_line() -> None:
    assert list(chunk_stream("abc")) == [
        Chunk("a", 1, 1),
        Chunk("b", 1, 2),
        Chunk("c", 1, 3),
    ]


def test_newline_will_increment_line_field() -> None:
    assert list(chunk_stream("a\nb")) == [
        Chunk("a", 1, 1),
        Chunk("\n", 1, 2),
        Chunk("b", 2, 1),
    ]


def test_group_basic_chunks() -> None:
    chunks = chunk_stream("abc")

    assert list(group_chunks(chunks)) == [
        Token("abc", line=1, column_start=1, column_end=3)
    ]


def test_group_chunks() -> None:
    chunks = chunk_stream("a b")

    assert list(group_chunks(chunks)) == [
        Token("a", 1, 1, 1),
        Token(" ", 1, 2, 2),
        Token("b", 1, 3, 3),
    ]


def test_whitespace_at_eof_is_included() -> None:
    assert list(group_chunks(chunk_stream("a "))) == [
        Token("a", 1, 1, 1),
        Token(" ", 1, 2, 2),
    ]


def test_group_strings_as_one_token() -> None:
    assert list(group_chunks(chunk_stream('"hello world"'))) == [
        Token('"hello world"', 1, 1, 13),
    ]

    assert list(group_chunks(chunk_stream("'hello world'"))) == [
        Token("'hello world'", 1, 1, 13),
    ]

    assert list(group_chunks(chunk_stream('"hello world" xyz'))) == [
        Token('"hello world"', 1, 1, 13),
        Token(" ", 1, 14, 14),
        Token("xyz", 1, 15, 17),
    ]


def test_group_comments_as_one_token() -> None:
    code = "line_1 # this is a comment\nline_2"

    tokens = list(group_chunks(chunk_stream(code)))

    assert tokens == [
        Token("line_1", 1, 1, 6),
        Token(" ", 1, 7, 7),
        Token("# this is a comment", 1, 8, 26),
        Token("\n", 1, 27, 27),
        Token("line_2", 2, 1, 6),
    ]


def test_group_leading_whitespace() -> None:
    code = """\
line_1
 line_2
  line_3

  line_4"""

    tokens = list(group_chunks(chunk_stream(code)))

    assert tokens == [
        Token("line_1", 1, 1, 6),
        Token("\n", 1, 7, 7),
        Token(" ", 2, 1, 1),
        Token("line_2", 2, 2, 7),
        Token("\n", 2, 8, 8),
        Token("  ", 3, 1, 2),
        Token("line_3", 3, 3, 8),
        Token("\n", 3, 9, 9),
        Token("\n", 4, 1, 1),
        Token("  ", 5, 1, 2),
        Token("line_4", 5, 3, 8),
    ]


def test_token_separators_create_their_own_tokens() -> None:
    for separator in TOKEN_SEPARATORS:
        code = f"a{separator}b"

        tokens = group_chunks(chunk_stream(code))

        assert [token.content for token in tokens] == ["a", separator, "b"]


def test_crlf_is_treated_as_newline() -> None:
    assert list(group_chunks(chunk_stream("a\r\nb"))) == [
        Token("a", 1, 1, 1),
        Token("\r\n", 1, 2, 3),
        Token("b", 2, 1, 1),
    ]


def test_multiple_crlf() -> None:
    assert list(group_chunks(chunk_stream("a\r\n\r\nb"))) == [
        Token("a", 1, 1, 1),
        Token("\r\n", 1, 2, 3),
        Token("\r\n", 2, 1, 2),
        Token("b", 3, 1, 1),
    ]


def test_basic_token_classification() -> None:
    for code, ty in TOKEN_SEPARATORS.items():
        tokens = list(tokenize(code))

        assert len(tokens) == 1
        assert isinstance(tokens[0], ty)


def test_float_literal_token_classification() -> None:
    tests = ("1.0", "12.0", "123.0", "3.1415")

    for test in tests:
        tokens = list(tokenize(test))

        assert len(tokens) == 1
        assert isinstance(tokens[0], FloatLiteralToken)


def test_int_literal_token_classification() -> None:
    tests = ("1", "12", "123")

    for test in tests:
        tokens = list(tokenize(test))

        assert len(tokens) == 1
        assert isinstance(tokens[0], IntegerLiteralToken)


def test_string_literal_token_classification() -> None:
    tests = ('"hello"', '"hello world"')

    for test in tests:
        tokens = list(tokenize(test))

        assert len(tokens) == 1
        assert isinstance(tokens[0], StringLiteralToken)


def test_bool_literal_token_classification() -> None:
    tests = ("true", "false")

    for test in tests:
        tokens = list(tokenize(test))

        assert len(tokens) == 1
        assert isinstance(tokens[0], BooleanLiteralToken)


def test_identifier_classification() -> None:
    tokens = list(tokenize("x y z"))

    assert len(tokens) == 5

    assert [type(token) for token in tokens] == [
        IdentifierToken,
        WhiteSpaceToken,
        IdentifierToken,
        WhiteSpaceToken,
        IdentifierToken,
    ]


def test_keyword_classification() -> None:
    for keyword, ty in KEYWORD_NAMES.items():
        tokens = list(tokenize(keyword))

        assert len(tokens) == 1
        assert isinstance(tokens[0], ty)


def test_unclosed_string_returns_error() -> None:
    wrapper = GeneratorWrapper(tokenize('"no closing quote'))
    result = list(wrapper)

    assert not result
    assert wrapper.value == "string was not closed"


def test_parse_identifier_with_dot() -> None:
    tokens = list(tokenize("a.b.c"))

    assert tokens == [IdentifierToken("a.b.c", 1, 1, 5)]


def test_classify_crlf() -> None:
    tokens = list(tokenize("\r\n"))

    match tokens:
        case [NewlineToken("\r\n", 1, 1, 1)]:
            return

    pytest.fail(f"Invalid token(s): {tokens}")


def test_utf8_bom_ignored() -> None:
    tokens = list(tokenize("\uFEFFabc"))

    match tokens:
        case [IdentifierToken("abc", 1, 2, 4)]:
            return

    pytest.fail(f"Invalid token(s): {tokens}")


def test_utf8_bom_not_at_start_is_error() -> None:
    msg = "BOM must be at the start of the file"

    with pytest.raises(ValueError, match=msg):
        list(tokenize("abc\uFEFF"))
