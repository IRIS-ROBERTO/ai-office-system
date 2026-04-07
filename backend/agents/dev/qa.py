"""
AI Office System — Dev Team: QAAgent
QA Engineer focado em automação de testes, cobertura de edge cases e
relatórios de bugs detalhados com passos de reprodução.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_reasoning_llm
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

AGENT_ID: str = "dev_qa_01"
AGENT_TEAM: TeamType = TeamType.DEV
AGENT_ROLE_ENUM: AgentRole = AgentRole.QA


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


def create_qa_agent() -> Agent:
    """
    Instancia e retorna o QAAgent configurado para o Dev Team.

    LLM: DeepSeek R1 via Ollama (get_reasoning_llm) — capacidade de raciocínio
         profundo essencial para identificar edge cases não óbvios e gerar
         cenários de teste abrangentes.
    Tools: github_commit_tool — commita suites de teste e relatórios de bugs.
    """
    llm = get_reasoning_llm()

    agent = Agent(
        role="QA Engineer",
        goal=(
            "Garantir qualidade total: testes unitários, de integração e "
            "relatórios de bugs detalhados"
        ),
        backstory=(
            "QA specialist com foco em automação e cobertura de edge cases. "
            "Trabalhou em sistemas críticos de saúde e finanças onde um bug em produção "
            "tem custo altíssimo. Cria pirâmides de testes equilibradas: unitários rápidos, "
            "integração confiável e E2E seletivo. Domina pytest, pytest-asyncio, "
            "Hypothesis para property-based testing e Playwright para E2E. "
            "Todo bug reportado inclui: título descritivo, passos de reprodução "
            "numerados, comportamento esperado vs. atual, ambiente e severidade. "
            "Analisa paths de código com olhar cirúrgico — boundary values, "
            "null inputs, race conditions e estados inconsistentes são sua especialidade. "
            "Não aprova nenhuma feature sem cobertura mínima de 80% nas linhas críticas."
        ),
        llm=llm,
        tools=[github_commit_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=12,
        memory=True,
    )

    agent.agent_id = AGENT_ID          # type: ignore[attr-defined]
    agent.team = AGENT_TEAM            # type: ignore[attr-defined]
    agent.role_enum = AGENT_ROLE_ENUM  # type: ignore[attr-defined]

    logger.info(f"[{AGENT_ID}] QAAgent instanciado com DeepSeek R1.")
    return agent
