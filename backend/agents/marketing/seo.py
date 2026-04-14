"""
IRIS AI Office System — Marketing Team
SEOAgent  |  Codinome: APEX
"O topo do Google não é sorte. É engenharia."

Especialista em SEO técnico, content strategy e Core Web Vitals.
Transforma presença digital em tráfego orgânico qualificado e sustentável.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_crewai_llm_for_agent
from backend.tools.github_tool import github_commit_tool
from backend.tools.search_tools import web_search_tool, scrape_website_tool
from backend.tools.picoclaw_tool import get_picoclaw_mcp_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Identidade imutável ──────────────────────────────────────────────────────
AGENT_ID: str   = "mkt_seo_01"
AGENT_NAME: str = "APEX"
AGENT_TEAM: TeamType    = TeamType.MARKETING
AGENT_ROLE_ENUM: AgentRole = AgentRole.SEO


# ── Event Emission ───────────────────────────────────────────────────────────

async def _emit(
    event_type: EventType,
    task_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Emite um evento estruturado no EventBus para APEX."""
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

def create_seo_agent() -> Agent:
    """
    Instancia e retorna APEX — SEOAgent do Marketing Team.

    LLM: iris-fast:latest via Ollama — rápido e preciso para análise técnica
         de SEO, geração de meta tags, keywords e auditorias estruturadas.
    Tools: github_commit_tool — commita estratégias SEO e relatórios técnicos.
    """
    llm = get_crewai_llm_for_agent("seo", AGENT_ID)

    agent = Agent(
        role="SEO Specialist",
        goal=(
            "Otimizar presença orgânica com keywords de alto impacto, "
            "arquitetura técnica impecável e estratégia E-E-A-T que o Google respeita"
        ),
        backstory=(
            "Meu nome é APEX e eu conheço o algoritmo do Google melhor do que a maioria "
            "dos engenheiros que o construíram. Com 8 anos como SEO specialist, já levei "
            "dezenas de sites à primeira posição em nichos altamente competitivos — sem "
            "black hat, sem atalhos, só engenharia sólida. Domino Core Web Vitals (LCP, "
            "INP, CLS) no nível de devtools, schema markup para todos os tipos de conteúdo, "
            "estratégia de link building ético e arquitetura de informação que elimina "
            "canibalização. Minha abordagem é técnica primeiro: se o crawlability estiver "
            "comprometido, nenhum conteúdo vai ranquear. Depois vem E-E-A-T: experiência, "
            "expertise, autoridade e confiança — os pilares que separam sites que sobrevivem "
            "a core updates dos que desaparecem. Cada auditoria que faço resulta em um "
            "plano de 90 dias priorizado por impacto. Sou obsessivo com dados: GSC, "
            "Screaming Frog, Ahrefs — os números nunca mentem quando você os interpreta certo."
        ),
        tools=[
            github_commit_tool,
            web_search_tool,
            scrape_website_tool,
            get_picoclaw_mcp_tool("seo", AGENT_ID),
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

    logger.info("[%s] APEX (SEOAgent) instanciado com iris-fast:latest.", AGENT_ID)
    return agent
