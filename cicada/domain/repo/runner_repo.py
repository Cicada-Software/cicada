from abc import ABC, abstractmethod

from cicada.ast.nodes import FileNode
from cicada.domain.runner import Runner, RunnerId
from cicada.domain.session import Session


class IRunnerRepo(ABC):
    @abstractmethod
    def get_runner_by_id(self, id: RunnerId) -> Runner | None:
        ...

    @abstractmethod
    def queue_session(
        self,
        session: Session,
        tree: FileNode,
        url: str,
    ) -> None:
        """
        Queue a session to be picked up by a self-hosted runner. This queue is
        in-memory, meaning workflows not picked up before server restart will
        be lost. This will be fixed in the future.
        """

    @abstractmethod
    def get_queued_sessions_for_runner(
        self, id: RunnerId
    ) -> list[tuple[Session, FileNode, str]]:
        """
        Return a list of sessions that have yet to be ran for a given runner.
        Sessions returned by this function must have been enqueued via the
        `queue_session_for_runner()` function above.

        This function returns all the information necessary for a runner to run
        a session: The session object itself, the AST tree of the workflow to
        run, and a URL for cloning the repository.

        It is the responsibility of the callee to update the session status for
        each session.

        It is assumed that the callee will handle the session after calling, so
        the calle will not be able to recieve the same session again.
        """
