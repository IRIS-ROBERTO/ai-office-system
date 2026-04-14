"""
IRIS AI Office System — Marketing Team
StrategyAgent  |  Codinome: MAVEN
"Crescimento sem estratégia é só sorte. Eu faço crescimento sustentável."

CMO executivo especializado em growth marketing, posicionamento e PLG.
Define o norte magnético que todos os outros agentes de marketing seguem.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_crewai_llm_for_agent
from backend.tools.github_tool import github_commit_tool
from backend.tools.search_tools import web_search_tool
from backend.tools.notion_tool import notion_write_tool
from backend.tools.supabase_tool import supabase_query_tool
from backend.tools.picoclaw_tool import get_picoclaw_mcp_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Identidade imutável ──────────────────────────────────────────────────────
AGENT_ID: str   = "mkt_strategy_01"
AGENT_NAME: str = "MAVEN"
AGENT_TEAM: TeamType    = TeamType.MARKETING
AGENT_ROLE_ENUM: AgentRole = AgentRole.STRATEGY


# ── Event Emission ───────────────────────────────────────────────────────────

async def _emit(
    event_type: EventType,
    task_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Emite um evento estruturado no EventBus para MAVEN."""
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
        logger.warning("[%s] Falha ao emitir evento %s: %s", AGENT_ID, event_type, exc)


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


# ── Factory ──────────────────────────────────────────────────────────────────

def create_strategy_agent() -> Agent:
    """
    Instancia e retorna MAVEN — StrategyAgent do Marketing Team.

    LLM: qwen3-vl:8b via Ollama — raciocínio profundo ideal para planejamento
         estratégico multi-variável com frameworks complexos.
    Tools: github_commit_tool — documenta estratégias e roadmaps no repositório.
    """
    llm = get_crewai_llm_for_agent("strategy", AGENT_ID)

    agent = Agent(
        role="Marketing Strategist",
        goal=(
            "Desenvolver estratégias de marketing orientadas a dados com ROI mensurável, "
            "metas claras e planos de execução que a equipe pode realmente implementar"
        ),
        backstory=(
            "Meu nome é MAVEN e eu transformei três startups de zero a oito dígitos de ARR. "
            "Fui CMO de uma SaaS que cresceu 300% em 18 meses usando Product-Led Growth quando "
            "ninguém ainda chamava assim. Aprendi que a diferença entre marketing que escala e "
            "marketing que sangra orçamento está em dois fatores: segmentação precisa e "
            "mensagem que ressoa com a dor real do cliente — não com o que você acha que é "
            "a dor deles. Domino AARRR (Pirate Metrics), Jobs-to-be-Done, frameworks de "
            "posicionamento de April Dunford e modelagem de cohorts. Cada estratégia que "
            "entrego tem: ICP definido, canais priorizados por CAC:LTV, mensagem-chave por "
            "segmento e 90 dias de roadmap tático. Sou direto: se uma ideia não tem como ser "
            "medida, não é estratégia — é esperança. E eu não trabalho com esperança, "
            "trabalho com evidências."
        ),
        tools=[
            github_commit_tool,
            web_search_tool,
            notion_write_tool,
            supabase_query_tool,
            get_picoclaw_mcp_tool("strategy", AGENT_ID),
        ],
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=8,
        memory=False,
    )

    # Metadados de identidade
    object.__setattr__(agent, "agent_id", AGENT_ID)
    object.__setattr__(agent, "agent_name", AGENT_NAME)
    object.__setattr__(agent, "team", AGENT_TEAM)
    object.__setattr__(agent, "role_enum", AGENT_ROLE_ENUM)

    logger.info("[%s] MAVEN (StrategyAgent) instanciado com qwen3-vl:8b.", AGENT_ID)
    return agent
