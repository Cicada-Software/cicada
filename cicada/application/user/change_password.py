from cicada.application.exceptions import Unauthorized
from cicada.domain.repo.user_repo import IUserRepo
from cicada.domain.user import PasswordHash, User


class ChangePassword:
    """
    Change a user's password. This should only be called by admins, or by users
    who have already been authenticated. This cannot be called on users who are
    authenticated via 3rd party providers, such as SSO logins with Github.
    """

    def __init__(self, user_repo: IUserRepo) -> None:
        self.user_repo = user_repo

    def handle(self, user: User, password: str) -> None:
        if user.provider != "cicada":
            raise Unauthorized("Only local users can change their password")

        user.password_hash = PasswordHash.from_password(password)

        self.user_repo.create_or_update_user(user)
