from cicada.api.application.exceptions import Unauthorized
from cicada.api.domain.user import User
from cicada.api.repo.user_repo import IUserRepo


class LocalUserLogin:
    """
    Login via a local user account (that is, not an externally managed SSO
    login such as GitHub). If the username or password doesn't match, the same
    error message is returned to prevent enumeration attacks.
    """

    def __init__(self, user_repo: IUserRepo) -> None:
        self.user_repo = user_repo

    def handle(self, username: str, password: str) -> User:
        if user := self.user_repo.get_user_by_username(username):
            if user.password_hash and user.password_hash.verify(password):
                self.user_repo.update_last_login(user)

                return user

        raise Unauthorized("Incorrect username or password")
