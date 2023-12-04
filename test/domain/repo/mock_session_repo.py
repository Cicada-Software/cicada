from collections import defaultdict

from cicada.domain.repo.repository_repo import Permission
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.session import Session, SessionId, Workflow, WorkflowId
from cicada.domain.user import User


class MockSessionRepo(ISessionRepo):
    sessions: dict[tuple[SessionId, int], Session]
    workflows: dict[WorkflowId, Workflow]
    workflow_sessions: defaultdict[SessionId, list[WorkflowId]]

    def __init__(self) -> None:
        self.sessions = {}
        self.workflows = {}
        self.workflow_sessions = defaultdict(list)

    def create(self, session: Session) -> None:
        self.sessions[(session.id, session.run)] = session

    def create_workflow(self, workflow: Workflow, session: Session) -> None:
        self.workflows[workflow.id] = workflow
        self.workflow_sessions[session.id].append(workflow.id)

    def update(self, session: Session) -> None:
        self.sessions[(session.id, session.run)] = session

    def update_workflow(self, workflow: Workflow) -> None:
        self.workflows[workflow.id] = workflow

    def get_session_by_session_id(
        self,
        uuid: SessionId,
        run: int = -1,
        user: User | None = None,
        *,
        permission: Permission | None = None,
    ) -> Session | None:
        if run == -1:
            run = max(run for id, run in self.sessions if id == uuid)

        session = self.sessions.get((uuid, run))

        if not session:
            return None

        for workflow_id in self.workflow_sessions.get(uuid, []):
            tmp = self.get_workflow_by_id(workflow_id)
            assert tmp
            session.runs.append(tmp)

        return session

    def get_recent_sessions(self, user: User) -> list[Session]:
        raise NotImplementedError

    def get_recent_sessions_for_repo(self, user: User, repository_url: str) -> list[Session]:
        raise NotImplementedError

    def get_runs_for_session(
        self,
        user: User,
        uuid: SessionId,
    ) -> Session | None:
        raise NotImplementedError

    def get_recent_sessions_as_admin(self) -> list[Session]:
        raise NotImplementedError

    def can_user_access_session(
        self,
        user: User,
        session: Session,
        *,
        permission: Permission,
    ) -> bool:
        raise NotImplementedError

    def get_workflow_id_from_session(self, session: Session) -> WorkflowId | None:
        for workflow_id in self.workflow_sessions.get(session.id, []):
            return workflow_id

        return None

    def get_workflow_by_id(self, uuid: WorkflowId) -> Workflow | None:
        return self.workflows.get(uuid)
