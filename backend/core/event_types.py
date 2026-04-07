"""
AI Office System — Event Types
Fonte de verdade para todos os eventos do sistema.
Toda animação visual deriva de um desses eventos.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime
import uuid


class EventType(str, Enum):
    # Ciclo de vida de tarefas
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_IN_PROGRESS = "task_in_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # Ciclo de vida de agentes
    AGENT_CALLED = "agent_called"
    AGENT_MOVING = "agent_moving"
    AGENT_ASSIGNED = "agent_assigned"
    AGENT_IDLE = "agent_idle"
    AGENT_THINKING = "agent_thinking"

    # Handoff entre agentes
    HANDOFF = "handoff"

    # Reuniões / colaboração
    MEETING_STARTED = "meeting_started"
    MEETING_FINISHED = "meeting_finished"

    # Sistema
    SYSTEM_ERROR = "system_error"
    SYSTEM_READY = "system_ready"

    # GitHub (agentes commitando)
    GIT_COMMIT = "git_commit"
    GIT_PUSH = "git_push"
    REPO_CREATED = "repo_created"


class TeamType(str, Enum):
    DEV = "dev"
    MARKETING = "marketing"


class AgentRole(str, Enum):
    # Dev Team
    PLANNER = "planner"
    FRONTEND = "frontend"
    BACKEND = "backend"
    QA = "qa"
    SECURITY = "security"
    DOCS = "docs"

    # Marketing Team
    RESEARCH = "research"
    STRATEGY = "strategy"
    CONTENT = "content"
    SEO = "seo"
    SOCIAL = "social"
    ANALYTICS = "analytics"

    # Senior (ambos os times)
    ORCHESTRATOR = "orchestrator"


# Mapeamento de cor por role (para o visual engine)
AGENT_COLORS = {
    AgentRole.RESEARCH: "#00C853",    # Verde
    AgentRole.FRONTEND: "#00C853",
    AgentRole.BACKEND: "#D50000",     # Vermelho
    AgentRole.PLANNER: "#2962FF",     # Azul
    AgentRole.STRATEGY: "#2962FF",
    AgentRole.QA: "#FFD600",          # Amarelo
    AgentRole.ANALYTICS: "#FFD600",
    AgentRole.SECURITY: "#AA00FF",    # Roxo
    AgentRole.DOCS: "#FF6D00",        # Laranja
    AgentRole.CONTENT: "#FF6D00",
    AgentRole.SEO: "#FF6D00",
    AgentRole.SOCIAL: "#FF6D00",
    AgentRole.ORCHESTRATOR: "#FFFFFF", # Branco — sênior
}


@dataclass
class OfficialEvent:
    """
    Todo evento emitido no sistema deve usar esta estrutura.
    Frontend e Visual Engine consomem exclusivamente esta classe.
    """
    event_type: EventType
    team: TeamType
    agent_id: str
    agent_role: AgentRole
    task_id: Optional[str] = None
    payload: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "team": self.team.value,
            "agent_id": self.agent_id,
            "agent_role": self.agent_role.value,
            "task_id": self.task_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
