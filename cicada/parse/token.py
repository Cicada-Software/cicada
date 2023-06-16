# fmt: off

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Self


@dataclass(frozen=True)
class Chunk:
    char: str
    line: int
    column: int


@dataclass
class Token:
    content: str
    line: int
    column_start: int
    column_end: int

    @classmethod
    def from_chunk(cls, chunk: Chunk) -> Self:
        return cls(chunk.char, chunk.line, chunk.column, chunk.column)

    @classmethod
    def meld(cls, tokens: Sequence[Self]) -> Self:
        content = "".join(token.content for token in tokens)

        return cls(**dict(asdict(tokens[0]), content=content))


class NewlineToken(Token): pass
class OpenBraceToken(Token): pass
class CloseBraceToken(Token): pass
class OpenParenToken(Token): pass
class CloseParenToken(Token): pass
class OpenBracketToken(Token): pass
class CloseBracketToken(Token): pass
class LessThanToken(Token): pass
class LessThanOrEqualToken(Token): pass
class GreaterThanToken(Token): pass
class GreaterThanOrEqualToken(Token): pass
class PowerToken(Token): pass
class AsteriskToken(Token): pass
class SlashToken(Token): pass
class PlusToken(Token): pass
class MinusToken(Token): pass
class ColonToken(Token): pass
class EqualToken(Token): pass
class DotToken(Token): pass
class CommaToken(Token): pass
class WhiteSpaceToken(Token): pass


class FloatLiteralToken(Token):
    # TODO: add literal value here
    pass


class IntegerLiteralToken(Token):
    # TODO: add literal value here
    pass


class StringLiteralToken(Token):
    # TODO: add literal value here
    pass


class BooleanLiteralToken(Token):
    # TODO: add literal value here
    pass


class DanglingToken(Token):
    """
    These are tokens which are uncategorized, but might have a purpose under
    certain circumstances. In general, they should cause an error unless a
    parser has a specific need to handle tokens in this manner.
    """


class CommentToken(Token):
    pass


class IdentifierToken(Token): pass


class KeywordToken(IdentifierToken):
    """
    Keywords are reserved words which have semantic meaning to Cicada. Keywords
    can be demoted to an IdentifierToken if they are not being used in the
    context of an expression or statement.

    For example, in the following example:

    shell return 1

    The "return" here is an identifier, because "shell" is a function call, and
    "return" is a string argument.

    In this example though:

    return 1

    "return" is a keyword, because it is used as a statement, not an argument
    to a function.
    """


class MutToken(KeywordToken): pass
class ReturnToken(KeywordToken): pass
class UnreachableToken(KeywordToken): pass
class IfToken(KeywordToken): pass
class ElifToken(KeywordToken): pass
class ElseToken(KeywordToken): pass
class WhileToken(KeywordToken): pass
class NoopToken(KeywordToken): pass
class BreakToken(KeywordToken): pass
class ContinueToken(KeywordToken): pass
class ImportToken(KeywordToken): pass
class ModToken(KeywordToken): pass
class NotToken(KeywordToken): pass
class AndToken(KeywordToken): pass
class OrToken(KeywordToken): pass
class XorToken(KeywordToken): pass
class LetToken(KeywordToken): pass
class OnToken(KeywordToken): pass
class WhereToken(KeywordToken): pass
class IsToken(KeywordToken): pass
class RunOnToken(KeywordToken): pass
