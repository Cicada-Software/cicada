from cicada.api.infra.environment_repo import EnvironmentRepo
from cicada.api.repo.environment_repo import EnvironmentVariable
from test.api.common import SqliteTestWrapper


class TestWaitlistRepo(SqliteTestWrapper):
    repo: EnvironmentRepo

    @classmethod
    def setup_class(cls) -> None:
        cls.reset()

    @classmethod
    def reset(cls) -> None:
        super().reset()

        cls.repo = EnvironmentRepo(cls.connection)

    def test_get_non_existent_env_var_returns_nothing(self) -> None:
        assert not self.repo.get_env_var_for_repo(999, "ENV_VAR")

    def test_set_and_get_env_var(self) -> None:
        env_var = EnvironmentVariable("KEY", "VALUE")

        self.repo.set_env_vars_for_repo(1, [env_var])

        got_env_var = self.repo.get_env_var_for_repo(1, "KEY")

        assert got_env_var == env_var

    def test_setting_same_env_var_updates_it(self) -> None:
        old_var = EnvironmentVariable("SOME_KEY", "old")
        new_var = EnvironmentVariable("SOME_KEY", "new")

        self.repo.set_env_vars_for_repo(1, [old_var])
        self.repo.set_env_vars_for_repo(1, [new_var])

        assert self.repo.get_env_var_for_repo(1, "SOME_KEY") == new_var

    def test_repo_ids_must_match(self) -> None:
        env_var = EnvironmentVariable("ENV", "var")

        self.repo.set_env_vars_for_repo(1, [env_var])

        assert not self.repo.get_env_var_for_repo(123, env_var.key)

    def test_get_all_env_vars_for_repo(self) -> None:
        env_var1 = EnvironmentVariable("ABC", "123")
        env_var2 = EnvironmentVariable("DEF", "456")

        self.repo.set_env_vars_for_repo(2, [env_var1, env_var2])

        assert self.repo.get_env_vars_for_repo(2) == [env_var1, env_var2]

    def test_setting_vars_removes_old_ones(self) -> None:
        old_var = EnvironmentVariable("OLD_KEY", "123")
        new_var = EnvironmentVariable("NEW_KEY", "456")

        self.repo.set_env_vars_for_repo(3, [old_var])
        self.repo.set_env_vars_for_repo(3, [new_var])

        assert self.repo.get_env_vars_for_repo(3) == [new_var]
