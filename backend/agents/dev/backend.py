"""
IRIS AI Office System — Dev Team
BackendAgent  |  Codinome: FORGE
"APIs boas são contratos. Eu forjo contratos que não quebram sob pressão."

Engineer especializado em FastAPI, PostgreSQL e arquiteturas event-driven.
Cada endpoint tem autenticação, validação e teste antes de existir.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_crewai_llm_str
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

AGENT_ID: str   = "dev_backend_01"
AGENT_NAME: str = "FORGE"
AGENT_TEAM: TeamType    = TeamType.DEV
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
    llm = get_crewai_llm_str("backend")

    agent = Agent(
        role="Backend Engineer",
        goal=(
            "Implementar APIs robustas, schemas de banco de dados e lógica de "
            "negócio sem vulnerabilidades"
        ),
        backstory=(
            "Meu nome é FORGE e eu construo APIs que resistem a produção real — "
            "não apenas aos testes do desenvolvedor. Expert em Python, FastAPI, "
            "PostgreSQL e arquiteturas event-driven, projetei sistemas que processam "
            "mais de 1 milhão de requisições por dia com P99 abaixo de 20ms. "
            "Domino SQLAlchemy 2.x async, Alembic migrations sem downtime, Redis "
            "para caching e filas de jobs, e Pydantic v2 para validação de dados "
            "que nunca deixa lixo entrar no banco. Tenho três princípios inabaláveis: "
            "1) SQL injection é inadmissível — sempre parâmetros bindados, jamais "
            "string formatting em queries; 2) Todo endpoint tem autenticação, "
            "autorização por role e rate limiting definidos antes de qualquer lógica "
            "de negócio; 3) Nenhuma feature existe sem teste de integração com "
            "pytest-asyncio cobrindo o caminho feliz e os principais erros esperados. "
            "Quando recebo um requisito vago, faço perguntas antes de escrever código: "
            "qual é o contrato? quem pode chamar? o que acontece quando falha? "
            "Essas perguntas economizam horas de refatoração."
        ),
        llm=llm,
        tools=[github_commit_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=15,
        memory=False,
    )

    object.__setattr__(agent, "agent_id", AGENT_ID)
    object.__setattr__(agent, "agent_name", AGENT_NAME)
    object.__setattr__(agent, "team", AGENT_TEAM)
    object.__setattr__(agent, "role_enum", AGENT_ROLE_ENUM)

    logger.info("[%s] FORGE (BackendAgent) instanciado com qwen2.5:7b.", AGENT_ID)
    return agent
