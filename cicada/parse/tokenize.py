import re
from collections.abc import Generator, Sequence
from dataclasses import asdict
from typing import Self

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
    "<=": LessThanOrEqualToken,
    ">": GreaterThanToken,
    ">=": GreaterThanOrEqualToken,
    "^": PowerToken,
    "*": AsteriskToken,
    "/": SlashToken,
    "+": PlusToken,
    "-": MinusToken,
    ":": ColonToken,
    "=": EqualToken,
    ",": CommaToken,
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
    "run_on": RunOnToken,
}


RESERVED_TOKENS = TOKEN_SEPARATORS | KEYWORD_NAMES


BOM = "\N{BYTE ORDER MARK}"


Error = str | None


class ChunkGrouper:
    tokens: list[Token]

    _token: Token | None

    _chunks: Sequence[Chunk]
    _chunk_index: int

    def __init__(self, chunks: Sequence[Chunk]) -> None:
        self._token = None
        self.tokens = []

        self._chunks = chunks
        self._chunk_index = 0

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Chunk:
        if self._chunk_index >= len(self._chunks):
            raise StopIteration()

        chunk = self._chunks[self._chunk_index]
        self._chunk_index += 1

        return chunk

    @property
    def current_chunk(self) -> Chunk:
        return self._chunks[self._chunk_index - 1]

    def append_chunk(self, chunk: Chunk) -> None:
        if self._token:
            self._token.content += chunk.char
            self._token.column_end += 1

        else:
            self._token = Token.from_chunk(chunk)

    def emit(self, chunk: Chunk | None = None) -> None:
        if self._token:
            self.tokens.append(self._token)
            self._token = None

        if chunk:
            self.tokens.append(Token.from_chunk(chunk))

    def rewind(self) -> None:
        self._chunk_index -= 1


def group_string(state: ChunkGrouper) -> None:
    quote = state.current_chunk.char

    state.append_chunk(state.current_chunk)

    for chunk in state:
        state.append_chunk(chunk)

        if chunk.char == quote:
            state.emit()
            return

    raise ValueError("string was not closed")


def group_crlf(state: ChunkGrouper) -> None:
    state.emit()
    state.append_chunk(state.current_chunk)

    newline = next(state, None)

    if not newline or newline.char != "\n":
        raise ValueError(r"Expected `\n`")

    state.append_chunk(newline)
    state.emit()


def group_comment(state: ChunkGrouper) -> None:
    state.append_chunk(state.current_chunk)

    for chunk in state:
        if chunk.char == "\n":
            state.emit(chunk)

            break

        state.append_chunk(chunk)


def group_whitespace(state: ChunkGrouper) -> None:
    state.emit()
    state.append_chunk(state.current_chunk)

    for chunk in state:
        c = chunk.char

        if c.isspace() and c not in "\r\n":
            state.append_chunk(chunk)

        else:
            state.emit()
            state.rewind()

            break


def group_multichar_operator(state: ChunkGrouper) -> None:
    current = state.current_chunk

    next_chunk = next(state, None)

    if next_chunk and next_chunk.char == "=":
        state.emit()
        state.append_chunk(current)
        state.append_chunk(next_chunk)
        state.emit()

    elif next_chunk:
        state.rewind()
        state.emit(current)

    else:
        state.emit(current)


def group_chunks(chunks: Sequence[Chunk]) -> list[Token]:
    state = ChunkGrouper(chunks)

    separators = {*TOKEN_SEPARATORS.keys(), BOM}

    for chunk in state:
        if chunk.char == "\r":
            group_crlf(state)

        elif chunk.char in ("<", ">"):
            group_multichar_operator(state)

        elif chunk.char in separators:
            state.emit(chunk)

        elif chunk.char.isspace():
            group_whitespace(state)

        elif chunk.char in ('"', "'"):
            group_string(state)

        elif chunk.char == "#":
            group_comment(state)

        else:
            state.append_chunk(chunk)

    state.emit()

    return state.tokens


INTEGER_REGEX = re.compile(r"^(\d+|0b[01]+|0x[A-Za-z0-9]+|0o[0-7]+)$")
FLOAT_REGEX = re.compile(r"\d+\.\d+")
IDENTIFIER_REGEX = re.compile(r"[._A-Za-z][_A-Za-z0-9\.]*")


def tokenize(code: str) -> Generator[Token, None, None]:
    tokens = group_chunks(list(chunk_stream(code)))

    for i, token in enumerate(tokens):
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

            yield NewlineToken(**data)

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
