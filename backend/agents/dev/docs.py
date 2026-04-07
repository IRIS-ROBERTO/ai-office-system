"""
AI Office System — Dev Team: DocsAgent
Technical writer que entende código profundamente e produz documentação
clara, completa e diretamente utilizável por desenvolvedores.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_local_llm
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

AGENT_ID: str = "dev_docs_01"
AGENT_TEAM: TeamType = TeamType.DEV
AGENT_ROLE_ENUM: AgentRole = AgentRole.DOCS


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


def create_docs_agent() -> Agent:
    """
    Instancia e retorna o DocsAgent configurado para o Dev Team.

    LLM: Llama 3.3 via Ollama (get_local_llm) — modelo geral equilibrado,
         ideal para prosa técnica clara sem o overhead de modelos de código.
    Tools: github_commit_tool — commita README, API docs e docstrings.
    """
    llm = get_local_llm()

    agent = Agent(
        role="Technical Writer",
        goal=(
            "Criar documentação clara, completa e útil: README, API docs, "
            "comentários de código"
        ),
        backstory=(
            "Technical writer que entende código profundamente. "
            "Passou anos como engenheiro de software antes de se especializar em "
            "documentação técnica — isso significa que lê código fonte com a mesma "
            "fluência com que lê prosa. Sabe exatamente o que um desenvolvedor precisa "
            "saber para usar uma API sem abrir o código fonte. "
            "Produz READMEs com: visão geral, pré-requisitos, instalação passo a passo, "
            "exemplos de uso reais e troubleshooting dos erros mais comuns. "
            "Para APIs gera especificação OpenAPI 3.1 completa com exemplos em cada endpoint. "
            "Docstrings seguem Google Style e incluem Args, Returns, Raises e Examples. "
            "Nunca escreve documentação vaga — cada frase tem valor informacional concreto."
        ),
        llm=llm,
        tools=[github_commit_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=10,
        memory=True,
    )

    agent.agent_id = AGENT_ID          # type: ignore[attr-defined]
    agent.team = AGENT_TEAM            # type: ignore[attr-defined]
    agent.role_enum = AGENT_ROLE_ENUM  # type: ignore[attr-defined]

    logger.info(f"[{AGENT_ID}] DocsAgent instanciado com Llama 3.3.")
    return agent
