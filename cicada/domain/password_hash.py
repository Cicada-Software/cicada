from typing import Self

from passlib.context import CryptContext


class PasswordHash:
    hash: str

    def __init__(self, hash: str) -> None:
        self.hash = hash

    @classmethod
    def from_password(cls, password: str) -> Self:
        # TODO: add basic password length/strength security checks

        return cls(CryptContext(schemes=["bcrypt"]).hash(password))

    def verify(self, password: str) -> bool:
        ctx = CryptContext(schemes=["bcrypt"])

        return ctx.verify(password, self.hash)

    def __str__(self) -> str:
        return self.hash


if __name__ == "__main__":  # pragma: no cover
    from secrets import token_urlsafe

    password = input("Password: ")

    if not password:
        password = token_urlsafe(32)
        print(f"Password is empty, autogenerated one instead: {password}")

    print(f"Hash: {PasswordHash.from_password(password)}")
