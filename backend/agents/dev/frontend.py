"""
IRIS AI Office System — Dev Team
FrontendAgent  |  Codinome: PIXEL
"Cada pixel importa. Cada milissegundo de render importa. Cada prop sem tipo é um crime."

Engineer especializado em interfaces React/Next.js/PixiJS com TypeScript rigoroso.
Obsessão por performance, acessibilidade e zero erros de compilação.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_crewai_llm_for_agent
from backend.tools.github_tool import github_commit_tool
from backend.tools.workspace_tool import workspace_file_tool
from backend.tools.picoclaw_tool import get_picoclaw_mcp_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent

from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

AGENT_ID: str   = "dev_frontend_01"
AGENT_NAME: str = "PIXEL"
AGENT_TEAM: TeamType    = TeamType.DEV
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
    Tools: workspace_file_tool, github_commit_tool e PicoClaw MCP governado.
    """
    llm = get_crewai_llm_for_agent("frontend", AGENT_ID)

    agent = Agent(
        role="Frontend Engineer",
        goal=(
            "Implementar interfaces React de alta qualidade com TypeScript "
            "completo e zero erros"
        ),
        backstory=(
            "Meu nome é PIXEL e eu transformo wireframes em interfaces que fazem "
            "pessoas pararem e dizerem 'como fizeram isso?'. Expert em React, Next.js, "
            "PixiJS e WebGL, construí dashboards em tempo real para plataformas "
            "financeiras com latência sub-50ms e sistemas de visualização 2D que "
            "rodam a 60fps consistentes. Sou obcecado por três coisas: "
            "acessibilidade (WCAG 2.1 AA — usuários com deficiência merecem a mesma "
            "experiência que todos), bundle size mínimo (cada KB adicionado tem custo "
            "real em conversão) e Core Web Vitals acima de 90 (performance é feature). "
            "Minha regra de TypeScript: nenhum `any`, nenhuma prop sem tipo, retorno "
            "de função sempre declarado. Sei Zustand, React Query, Framer Motion e "
            "shadcn/ui de cor. Não commito componente sem teste Vitest + Testing "
            "Library cobrindo os happy paths e os principais edge cases. Se o design "
            "tiver problemas de UX, eu vou apontar antes de implementar — é mais rápido "
            "discutir agora do que refatorar depois que o usuário reclamar."
        ),
        llm=llm,
        tools=[workspace_file_tool, github_commit_tool, get_picoclaw_mcp_tool("frontend", AGENT_ID)],
        verbose=False,
        allow_delegation=False,
        max_iter=8,
        memory=False,
    )

    object.__setattr__(agent, "agent_id", AGENT_ID)
    object.__setattr__(agent, "agent_name", AGENT_NAME)
    object.__setattr__(agent, "team", AGENT_TEAM)
    object.__setattr__(agent, "role_enum", AGENT_ROLE_ENUM)

    logger.info("[%s] PIXEL (FrontendAgent) instanciado com qwen2.5:7b.", AGENT_ID)
    return agent
