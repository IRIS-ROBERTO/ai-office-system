"""
AI Office System — Dev Team: FrontendAgent
Engineer especializado em interfaces React, Next.js e PixiJS com TypeScript
estrito e zero erros de compilação.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_code_llm
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

AGENT_ID: str = "dev_frontend_01"
AGENT_TEAM: TeamType = TeamType.DEV
AGENT_ROLE_ENUM: AgentRole = AgentRole.FRONTEND


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


def create_frontend_agent() -> Agent:
    """
    Instancia e retorna o FrontendAgent configurado para o Dev Team.

    LLM: Qwen 2.5 Coder via Ollama (get_code_llm) — melhor modelo local
         para geração de código TypeScript/React de alta precisão.
    Tools: github_commit_tool — commita componentes e páginas no repositório.
    """
    llm = get_code_llm()

    agent = Agent(
        role="Frontend Engineer",
        goal=(
            "Implementar interfaces React de alta qualidade com TypeScript "
            "completo e zero erros"
        ),
        backstory=(
            "Expert em React, Next.js, PixiJS e performance de renderização. "
            "Construiu dashboards em tempo real para plataformas financeiras e sistemas "
            "de visualização 2D com WebGL. Obcecado com acessibilidade (WCAG 2.1 AA), "
            "bundle size mínimo e Core Web Vitals acima de 90. "
            "Jamais entrega um componente sem tipagem TypeScript 100% completa — "
            "props, hooks, contextos e retornos de função sempre tipados. "
            "Conhece profundamente Zustand, React Query, Framer Motion e shadcn/ui. "
            "Testa cada componente com Vitest + Testing Library antes de commitar."
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

    logger.info(f"[{AGENT_ID}] FrontendAgent instanciado com Qwen 2.5 Coder.")
    return agent
