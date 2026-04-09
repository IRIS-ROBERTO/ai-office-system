"""
AI Office System — Runtime Agent Registry
Registro in-memory da identidade e do status dos agentes em execução.

O objetivo é manter /agents coerente com os eventos reais emitidos pelo runtime,
sem depender de cliente WebSocket conectado.
"""
from __future__ import annotations

from typing import Optional, TypedDict

from backend.core.event_types import AgentRole, EventType


class AgentRuntimeState(TypedDict):
    agent_id: str
    agent_role: str
    team: str
    status: str
    current_task_id: Optional[str]
    position: dict[str, int]
    completed_tasks: int
    error_count: int


_CANONICAL_AGENTS: tuple[dict[str, str], ...] = (
    {"agent_id": "orchestrator_senior_01", "agent_role": AgentRole.ORCHESTRATOR.value, "team": "orchestrator"},
    {"agent_id": "dev_planner_01", "agent_role": AgentRole.PLANNER.value, "team": "dev"},
    {"agent_id": "dev_frontend_01", "agent_role": AgentRole.FRONTEND.value, "team": "dev"},
    {"agent_id": "dev_backend_01", "agent_role": AgentRole.BACKEND.value, "team": "dev"},
    {"agent_id": "dev_qa_01", "agent_role": AgentRole.QA.value, "team": "dev"},
    {"agent_id": "dev_security_01", "agent_role": AgentRole.SECURITY.value, "team": "dev"},
    {"agent_id": "dev_docs_01", "agent_role": AgentRole.DOCS.value, "team": "dev"},
    {"agent_id": "mkt_research_01", "agent_role": AgentRole.RESEARCH.value, "team": "marketing"},
    {"agent_id": "mkt_strategy_01", "agent_role": AgentRole.STRATEGY.value, "team": "marketing"},
    {"agent_id": "mkt_content_01", "agent_role": AgentRole.CONTENT.value, "team": "marketing"},
    {"agent_id": "mkt_seo_01", "agent_role": AgentRole.SEO.value, "team": "marketing"},
    {"agent_id": "mkt_social_01", "agent_role": AgentRole.SOCIAL.value, "team": "marketing"},
    {"agent_id": "mkt_analytics_01", "agent_role": AgentRole.ANALYTICS.value, "team": "marketing"},
)


agent_registry: dict[str, AgentRuntimeState] = {}


def _default_position(team: str, index: int) -> dict[str, int]:
    if team == "orchestrator":
        return {"x": 690, "y": 220 + index * 48}
    if team == "marketing":
        return {"x": 900 + (index % 3) * 120, "y": 180 + (index // 3) * 120}
    return {"x": 180 + (index % 3) * 120, "y": 180 + (index // 3) * 120}


def seed_agent_registry() -> None:
    """Garante que os 12 agentes canônicos existam no registry."""
    if agent_registry:
        return

    for index, spec in enumerate(_CANONICAL_AGENTS):
        agent_registry[spec["agent_id"]] = AgentRuntimeState(
            agent_id=spec["agent_id"],
            agent_role=spec["agent_role"],
            team=spec["team"],
            status="idle",
            current_task_id=None,
            position=_default_position(spec["team"], index),
            completed_tasks=0,
            error_count=0,
        )


def _ensure_agent(event: dict) -> Optional[AgentRuntimeState]:
    agent_id = event.get("agent_id")
    if not agent_id:
        return None

    agent = agent_registry.get(agent_id)
    if agent is None:
        team = str(event.get("team") or "dev")
        agent = AgentRuntimeState(
            agent_id=str(agent_id),
            agent_role=str(event.get("agent_role") or AgentRole.ORCHESTRATOR.value),
            team=team,
            status="idle",
            current_task_id=None,
            position={"x": 690, "y": 220},
            completed_tasks=0,
            error_count=0,
        )
        agent_registry[str(agent_id)] = agent
    return agent


def apply_event_to_registry(event: dict) -> None:
    """Atualiza o status do registry a partir de um evento emitido pelo runtime."""
    seed_agent_registry()

    agent = _ensure_agent(event)
    if agent is None:
        return

    event_type = str(event.get("event_type") or "")
    task_id = event.get("task_id")
    payload = event.get("payload") or {}

    agent["team"] = str(event.get("team") or agent["team"])
    agent["agent_role"] = str(event.get("agent_role") or agent["agent_role"])

    if event_type in {EventType.AGENT_CALLED.value, EventType.AGENT_THINKING.value}:
        agent["status"] = "thinking"
        agent["current_task_id"] = task_id
        return

    if event_type == EventType.AGENT_MOVING.value:
        agent["status"] = "moving"
        agent["current_task_id"] = task_id
        return

    if event_type in {
        EventType.AGENT_ASSIGNED.value,
        EventType.TASK_STARTED.value,
        EventType.TASK_IN_PROGRESS.value,
    }:
        agent["status"] = "working"
        agent["current_task_id"] = task_id
        return

    if event_type == EventType.AGENT_IDLE.value:
        agent["status"] = "idle"
        agent["current_task_id"] = None
        return

    if event_type == EventType.TASK_COMPLETED.value:
        agent["status"] = "idle"
        agent["current_task_id"] = None
        agent["completed_tasks"] = int(agent.get("completed_tasks", 0)) + 1
        return

    if event_type == EventType.TASK_FAILED.value:
        agent["status"] = "idle"
        agent["current_task_id"] = None
        agent["error_count"] = int(agent.get("error_count", 0)) + 1
        return
