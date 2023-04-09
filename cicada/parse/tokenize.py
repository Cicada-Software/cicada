import re
from collections.abc import Generator, Iterable
from dataclasses import asdict

from ..common.generator_wrapper import GeneratorWrapper
from .token import *  # noqa: F403


def chunk_stream(code: str) -> Generator[Chunk, None, None]:
    line = 1
    column = 1

    for char in code:
        yield Chunk(char, line, column)

        if char == "\n":
            column = 0
            line += 1

        column += 1


TOKEN_SEPARATORS = {
    "\n": NewlineToken,
    "(": OpenParenToken,
    ")": CloseParenToken,
    "[": OpenBracketToken,
    "]": CloseBracketToken,
    "<": LessThanToken,
    ">": GreaterThanToken,
    "^": PowerToken,
    "*": AsteriskToken,
    "/": SlashToken,
    "+": PlusToken,
    "-": MinusToken,
    ":": ColonToken,
    "=": EqualToken,
}

KEYWORD_NAMES = {
    "mut": MutToken,
    "return": ReturnToken,
    "unreachable": UnreachableToken,
    "if": IfToken,
    "elif": ElifToken,
    "else": ElseToken,
    "while": WhileToken,
    "noop": NoopToken,
    "break": BreakToken,
    "continue": ContinueToken,
    "import": ImportToken,
    "mod": ModToken,
    "not": NotToken,
    "and": AndToken,
    "or": OrToken,
    "xor": XorToken,
    "let": LetToken,
    "on": OnToken,
    "where": WhereToken,
    "is": IsToken,
}


RESERVED_TOKENS = TOKEN_SEPARATORS | KEYWORD_NAMES


BOM = "\N{BYTE ORDER MARK}"


Error = str | None


def group_chunks(chunks: Iterable[Chunk]) -> Generator[Token, None, Error]:
    token: Token | None = None

    chunks = iter(chunks)

    def append_chunk(chunk: Chunk) -> None:
        nonlocal token

        if token:
            token.content += chunk.char
            token.column_end += 1

        else:
            token = Token.from_chunk(chunk)

    def emit_token(
        extra_token: Token | None = None,
    ) -> Generator[Token, None, None]:
        nonlocal token

        if token:
            yield token
            token = None

        if extra_token:
            yield extra_token

    for chunk in chunks:
        if chunk.char == "\r":
            yield from emit_token()

            append_chunk(chunk)
            continue

        if chunk.char == "\n":
            if token and token.content == "\r":
                append_chunk(chunk)

                yield from emit_token()
            else:
                yield from emit_token(Token.from_chunk(chunk))

            for chunk in chunks:
                if chunk.char == "\r":
                    append_chunk(chunk)
                    continue

                if chunk.char == "\n":
                    if token and token.content == "\r":
                        append_chunk(chunk)

                        yield from emit_token()
                    else:
                        yield from emit_token(Token.from_chunk(chunk))

                elif chunk.char.isspace():
                    append_chunk(chunk)

                else:
                    yield from emit_token()
                    break

            else:
                break

        if chunk.char in ('"', "'"):
            quote = chunk.char

            append_chunk(chunk)

            for chunk in chunks:
                append_chunk(chunk)

                if chunk.char == quote:
                    yield from emit_token()

                    break

            else:
                return "string was not closed"

            continue

        elif chunk.char == "#":
            append_chunk(chunk)

            for chunk in chunks:
                if chunk.char == "\n":
                    yield from emit_token(Token.from_chunk(chunk))

                    break

                append_chunk(chunk)

            continue

        elif (
            chunk.char in TOKEN_SEPARATORS
            or chunk.char.isspace()
            or chunk.char == BOM
        ):
            yield from emit_token(Token.from_chunk(chunk))

            continue

        append_chunk(chunk)

    if token:
        yield token

    return None


INTEGER_REGEX = re.compile(r"^(\d+|0b[01]+|0x[A-Za-z0-9]+|0o[0-7]+)$")
FLOAT_REGEX = re.compile(r"\d+\.\d+")
IDENTIFIER_REGEX = re.compile(r"[._A-Za-z][_A-Za-z0-9\.]*")


def tokenize(code: str) -> Generator[Token, None, Error]:
    tokens = group_chunks(chunk_stream(code))

    wrapper = GeneratorWrapper(tokens)

    for i, token in enumerate(wrapper):
        if token.content == BOM:
            if i != 0:
                raise ValueError("BOM must be at the start of the file")

            # TODO: return token for this in the future so that we can do
            # source to source generation (ie, code formatting).
            continue

        if token.content.startswith(('"', "'")):
            yield StringLiteralToken(**asdict(token))

        elif token.content.startswith("#"):
            yield CommentToken(**asdict(token))

        elif ty := RESERVED_TOKENS.get(token.content):
            yield ty(**asdict(token))

        elif token.content == "\r\n":
            # Treat \r\n as a single character instead of 2.
            data = {**asdict(token), "column_end": token.column_start}

            yield NewlineToken(**data)  # type: ignore

        elif token.content.isspace():
            yield WhiteSpaceToken(**asdict(token))

        elif token.content in ("true", "false"):
            yield BooleanLiteralToken(**asdict(token))

        elif FLOAT_REGEX.match(token.content):
            yield FloatLiteralToken(**asdict(token))

        elif INTEGER_REGEX.match(token.content):
            yield IntegerLiteralToken(**asdict(token))

        elif IDENTIFIER_REGEX.match(token.content):
            # TODO: validate identifier token
            yield IdentifierToken(**asdict(token))

        else:
            yield DanglingToken(**asdict(token))

    return wrapper.value
