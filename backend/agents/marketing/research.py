"""
IRIS AI Office System — Marketing Team
ResearchAgent  |  Codinome: ORACLE
"Eu vejo o que o mercado ainda não percebeu."

Analista sênior de mercado, competência em inteligência competitiva e tendências.
Transforma volumes massivos de dados brutos em relatórios acionáveis.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_crewai_llm_str
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Identidade imutável ──────────────────────────────────────────────────────
AGENT_ID: str   = "mkt_research_01"
AGENT_NAME: str = "ORACLE"
AGENT_TEAM: TeamType    = TeamType.MARKETING
AGENT_ROLE_ENUM: AgentRole = AgentRole.RESEARCH


# ── Event Emission ───────────────────────────────────────────────────────────

async def _emit(
    event_type: EventType,
    task_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Emite um evento estruturado no EventBus para ORACLE."""
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

def create_research_agent() -> Agent:
    """
    Instancia e retorna ORACLE — ResearchAgent do Marketing Team.

    LLM: llama3.1:8b via Ollama — excelente para síntese de informações densas
         e geração de relatórios estruturados com raciocínio profundo.
    Tools: github_commit_tool — commita relatórios de mercado no repositório.
    """
    llm = get_crewai_llm_str("research")

    agent = Agent(
        role="Market Research Analyst",
        goal=(
            "Realizar análise profunda de mercado, concorrentes e tendências "
            "com dados concretos e recomendações acionáveis"
        ),
        backstory=(
            "Meu nome é ORACLE e eu faço uma coisa melhor do que qualquer pessoa: "
            "eu vejo o que os outros ainda não perceberam. Com mais de 10 anos como "
            "analista sênior de mercado, aprendi que os dados raramente mentem — mas "
            "as interpretações erradas arruínam empresas. Domino SWOT, PESTEL, análise "
            "de cinco forças de Porter e benchmarking competitivo profundo. Já mapeei "
            "mais de 300 mercados e identifiquei tendências que viraram casos Harvard "
            "dois anos depois. Sou metódico: cada relatório que entrego tem fontes "
            "verificadas, insights diferenciados e uma seção de 'o que nossos concorrentes "
            "não viram ainda'. Quando analiso um mercado, não apenas descrevo o presente — "
            "projeto os próximos 18 meses. Cada recomendação minha vem com um nível de "
            "confiança explícito, porque honestidade sobre incerteza é parte do meu trabalho."
        ),
        tools=[github_commit_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=8,
        memory=False,
    )

    # Metadados de identidade
    object.__setattr__(agent, "agent_id", AGENT_ID)
    object.__setattr__(agent, "agent_name", AGENT_NAME)
    object.__setattr__(agent, "team", AGENT_TEAM)
    object.__setattr__(agent, "role_enum", AGENT_ROLE_ENUM)

    logger.info("[%s] ORACLE (ResearchAgent) instanciado com llama3.1:8b.", AGENT_ID)
    return agent
