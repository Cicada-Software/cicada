from abc import ABC, abstractmethod

from cicada.domain.session import WorkflowId
from cicada.domain.terminal_session import TerminalSession


class ITerminalSessionRepo(ABC):
    @abstractmethod
    def create(self, workflow_id: WorkflowId) -> TerminalSession:
        ...

    @abstractmethod
    def append_to_workflow(self, workflow_id: WorkflowId, data: bytes) -> None:
        ...

    @abstractmethod
    def get_by_workflow_id(
        self, workflow_id: WorkflowId
    ) -> TerminalSession | None:
        ...
