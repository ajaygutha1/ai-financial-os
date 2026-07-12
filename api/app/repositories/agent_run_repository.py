import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.agent_run import AgentRun, AgentRunStatus


class AgentRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, agent_run_id: uuid.UUID) -> AgentRun | None:
        return self.db.get(AgentRun, agent_run_id)

    def create(
        self,
        *,
        user_id: uuid.UUID,
        agent_name: str,
        prompt_version: str,
        user_message: str | None,
    ) -> AgentRun:
        run = AgentRun(
            user_id=user_id,
            agent_name=agent_name,
            prompt_version=prompt_version,
            user_message=user_message,
            status=AgentRunStatus.RUNNING,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def mark_completed(self, run: AgentRun) -> None:
        run.status = AgentRunStatus.COMPLETED
        run.completed_at = datetime.now(UTC)
        self.db.flush()

    def mark_failed(self, run: AgentRun, *, error_message: str) -> None:
        run.status = AgentRunStatus.FAILED
        run.error_message = error_message
        run.completed_at = datetime.now(UTC)
        self.db.flush()
