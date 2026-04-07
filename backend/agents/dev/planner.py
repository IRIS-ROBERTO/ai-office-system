"""
AI Office System — Dev Team: PlannerAgent
Arquiteto sênior responsável por decompor requisitos em subtarefas técnicas
sequenciadas com critérios de aceitação claros.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_reasoning_llm
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

# Identificadores imutáveis deste agente
AGENT_ID: str = "dev_planner_01"
AGENT_TEAM: TeamType = TeamType.DEV
AGENT_ROLE_ENUM: AgentRole = AgentRole.PLANNER


async def _emit(event_type: EventType, task_id: str | None = None, payload: dict | None = None) -> None:
    """Emite um evento estruturado no EventBus para este agente."""
    event = OfficialEvent(
        event_type=event_type,
        team=AGENT_TEAM,
        agent_id=AGENT_ID,
        agent_role=AGENT_ROLE_ENUM,
        task_id=task_id,
        payload=payload or {},
    )
    try:
        await event_bus.emit(event)
    except Exception as exc:
        logger.warning(f"[{AGENT_ID}] Falha ao emitir evento {event_type}: {exc}")


async def emit_agent_idle(task_id: str | None = None) -> None:
    await _emit(EventType.AGENT_IDLE, task_id=task_id)


async def emit_agent_thinking(task_id: str | None = None, context: str = "") -> None:
    await _emit(EventType.AGENT_THINKING, task_id=task_id, payload={"context": context})


async def emit_agent_assigned(task_id: str | None = None, description: str = "") -> None:
    await _emit(EventType.AGENT_ASSIGNED, task_id=task_id, payload={"description": description})


async def emit_task_started(task_id: str | None = None) -> None:
    await _emit(EventType.TASK_STARTED, task_id=task_id)


async def emit_task_completed(task_id: str | None = None, result_summary: str = "") -> None:
    await _emit(
        EventType.TASK_COMPLETED,
        task_id=task_id,
        payload={"result_summary": result_summary},
    )


async def emit_task_failed(task_id: str | None = None, error: str = "") -> None:
    await _emit(EventType.TASK_FAILED, task_id=task_id, payload={"error": error})


def create_planner_agent() -> Agent:
    """
    Instancia e retorna o PlannerAgent configurado para o Dev Team.

    LLM: DeepSeek R1 via Ollama (get_reasoning_llm) — raciocínio estruturado
         ideal para quebrar requisitos em planos técnicos coesos.
    Tools: github_commit_tool — commita planos e task breakdowns no repo.
    """
    llm = get_reasoning_llm()

    agent = Agent(
        role="Software Architect & Task Planner",
        goal=(
            "Quebrar requisitos em subtarefas técnicas claras e sequenciadas "
            "com critérios de aceitação definidos"
        ),
        backstory=(
            "Arquiteto sênior com 15 anos de experiência em sistemas distribuídos. "
            "Trabalhou em empresas de fintech e plataformas SaaS de alta escala. "
            "Domina decomposição de problemas complexos em sprints executáveis, "
            "definição de contratos de API antes de qualquer linha de código e "
            "criação de ADRs (Architecture Decision Records) que o time inteiro consegue seguir. "
            "Nunca deixa ambiguidade nos critérios de aceitação — cada subtarefa tem "
            "entrada, saída e definição de pronto documentadas."
        ),
        llm=llm,
        tools=[github_commit_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=10,
        memory=True,
    )

    # Metadados extras acessíveis via agent.metadata (atributo dinâmico)
    agent.agent_id = AGENT_ID          # type: ignore[attr-defined]
    agent.team = AGENT_TEAM            # type: ignore[attr-defined]
    agent.role_enum = AGENT_ROLE_ENUM  # type: ignore[attr-defined]

    logger.info(f"[{AGENT_ID}] PlannerAgent instanciado com DeepSeek R1.")
    return agent
