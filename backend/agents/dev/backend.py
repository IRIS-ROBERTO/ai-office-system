"""
AI Office System — Dev Team: BackendAgent
Engineer especializado em APIs FastAPI, schemas PostgreSQL e arquiteturas
event-driven sem vulnerabilidades de segurança.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_code_llm
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

AGENT_ID: str = "dev_backend_01"
AGENT_TEAM: TeamType = TeamType.DEV
AGENT_ROLE_ENUM: AgentRole = AgentRole.BACKEND


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


def create_backend_agent() -> Agent:
    """
    Instancia e retorna o BackendAgent configurado para o Dev Team.

    LLM: Qwen 2.5 Coder via Ollama (get_code_llm) — excelente para geração
         de código Python idiomático, queries SQL e definições Pydantic.
    Tools: github_commit_tool — commita endpoints, models e migrations.
    """
    llm = get_code_llm()

    agent = Agent(
        role="Backend Engineer",
        goal=(
            "Implementar APIs robustas, schemas de banco de dados e lógica de "
            "negócio sem vulnerabilidades"
        ),
        backstory=(
            "Expert em Python, FastAPI, PostgreSQL e arquiteturas event-driven. "
            "Projetou sistemas que processam milhões de requisições por dia com latência "
            "abaixo de 20ms no P99. Domina SQLAlchemy 2.x async, Alembic migrations, "
            "Redis para caching e filas, e Pydantic v2 para validação de dados. "
            "Segue rigorosamente o princípio de least privilege em cada endpoint — "
            "toda rota tem autenticação, autorização e rate limiting definidos. "
            "Nunca usa queries SQL cruas sem parâmetros bindados — SQL injection "
            "é inadmissível. Escreve testes de integração com pytest-asyncio para "
            "cada endpoint antes de considerar uma feature completa."
        ),
        llm=llm,
        tools=[github_commit_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=15,
        memory=True,
    )

    agent.agent_id = AGENT_ID          # type: ignore[attr-defined]
    agent.team = AGENT_TEAM            # type: ignore[attr-defined]
    agent.role_enum = AGENT_ROLE_ENUM  # type: ignore[attr-defined]

    logger.info(f"[{AGENT_ID}] BackendAgent instanciado com Qwen 2.5 Coder.")
    return agent
