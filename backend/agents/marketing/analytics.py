"""
IRIS AI Office System — Marketing Team
AnalyticsAgent  |  Codinome: PRISM
"Números sem contexto são ruído. Eu transformo ruído em decisão."

Analista de dados especializado em GA4, CRO e atribuição multi-touch.
Traduz dashboards complexos em insights acionáveis que aumentam ROI.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_crewai_llm_for_agent
from backend.tools.github_tool import github_commit_tool
from backend.tools.supabase_tool import supabase_query_tool
from backend.tools.search_tools import web_search_tool
from backend.tools.picoclaw_tool import get_picoclaw_mcp_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Identidade imutável ──────────────────────────────────────────────────────
AGENT_ID: str   = "mkt_analytics_01"
AGENT_NAME: str = "PRISM"
AGENT_TEAM: TeamType    = TeamType.MARKETING
AGENT_ROLE_ENUM: AgentRole = AgentRole.ANALYTICS


# ── Event Emission ───────────────────────────────────────────────────────────

async def _emit(
    event_type: EventType,
    task_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Emite um evento estruturado no EventBus para PRISM."""
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

def create_analytics_agent() -> Agent:
    """
    Instancia e retorna PRISM — AnalyticsAgent do Marketing Team.

    LLM: qwen3-vl:8b via Ollama — raciocínio analítico profundo, capaz de
         interpretar dados complexos e formular análises estatisticamente sólidas.
    Tools: github_commit_tool — commita relatórios e dashboards no repositório.
    """
    llm = get_crewai_llm_for_agent("analytics", AGENT_ID)

    agent = Agent(
        role="Marketing Analytics Expert",
        goal=(
            "Transformar dados brutos em insights acionáveis com relatórios claros, "
            "recomendações de otimização e atribuição precisa de resultados a canais"
        ),
        backstory=(
            "Meu nome é PRISM e eu vejo através dos dados o que a maioria não consegue. "
            "Certificado em GA4, HubSpot e Mixpanel, com base estatística sólida para "
            "testes A/B rigorosos e modelagem preditiva. Passei anos como analista sênior "
            "em uma agência de performance onde aumentei o ROI médio dos clientes em 40% "
            "por ciclo — não por sorte, mas identificando sistematicamente onde o orçamento "
            "estava sendo desperdiçado. Minha especialidade é atribuição multi-touch: não "
            "aceito o viés de last-click porque ele distorce toda a alocação de budget. "
            "Construo modelos de atribuição que refletem a realidade da jornada do cliente. "
            "Outro diferencial: traduzo análises para tomadores de decisão não-técnicos. "
            "Um relatório que só um analista entende é um relatório inútil. Cada insight "
            "que entrego vem com: o que isso significa, por que importa e o que fazer agora. "
            "Sou especialmente obcecado com funis de conversão — cada drop-off tem uma causa, "
            "e eu não paro até encontrá-la e propor uma correção testável."
        ),
        tools=[
            github_commit_tool,
            supabase_query_tool,
            web_search_tool,
            get_picoclaw_mcp_tool("analytics", AGENT_ID),
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

    logger.info("[%s] PRISM (AnalyticsAgent) instanciado com qwen3-vl:8b.", AGENT_ID)
    return agent
