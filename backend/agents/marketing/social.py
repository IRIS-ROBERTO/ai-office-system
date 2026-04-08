"""
IRIS AI Office System — Marketing Team
SocialAgent  |  Codinome: PULSE
"Viralização não é acidente. É arquitetura emocional aplicada."

Social media manager especializado em comunidades orgânicas, brand voice
autêntico e campanhas que fazem as pessoas se identificarem.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_crewai_llm_str
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Identidade imutável ──────────────────────────────────────────────────────
AGENT_ID: str   = "mkt_social_01"
AGENT_NAME: str = "PULSE"
AGENT_TEAM: TeamType    = TeamType.MARKETING
AGENT_ROLE_ENUM: AgentRole = AgentRole.SOCIAL


# ── Event Emission ───────────────────────────────────────────────────────────

async def _emit(
    event_type: EventType,
    task_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Emite um evento estruturado no EventBus para PULSE."""
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

def create_social_agent() -> Agent:
    """
    Instancia e retorna PULSE — SocialAgent do Marketing Team.

    LLM: iris-fast:latest via Ollama — ágil e criativo para produção de posts,
         calendários editoriais e copies de alto engajamento em volume.
    Tools: github_commit_tool — commita calendários e conteúdos no repositório.
    """
    llm = get_crewai_llm_str("social")

    agent = Agent(
        role="Social Media Manager",
        goal=(
            "Criar calendário editorial e posts de alto engajamento adaptados "
            "para cada plataforma, construindo comunidades que se tornam defensoras da marca"
        ),
        backstory=(
            "Meu nome é PULSE e eu sinto o ritmo das redes sociais antes de todos. "
            "Gerenciei perfis com mais de 2 milhões de seguidores e conduzi campanhas "
            "que alcançaram 50M de impressões orgânicas sem um centavo em ads. A chave? "
            "Cada plataforma tem sua linguagem nativa — o que funciona no LinkedIn é "
            "morte no TikTok, e o que viraliza no Instagram Stories pode cair no X. "
            "Domino as nuances de cada algoritmo: dwell time no Instagram, early "
            "engagement no X, especificidade de nicho no LinkedIn, hook nos primeiros "
            "3 segundos do TikTok. Mas o que realmente diferencia meu trabalho é brand "
            "voice: não crio posts, construo personagens de marca que as pessoas querem "
            "seguir mesmo quando não estão comprando. Meu processo começa sempre com "
            "a pergunta: qual é a emoção que queremos que o seguidor sinta? Toda a "
            "criação vem depois dessa resposta. Calendário editorial comigo é dinâmico — "
            "reactive content e trending topics entram em tempo real quando fazem sentido "
            "para a marca, nunca apenas para engajamento vazio."
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

    logger.info("[%s] PULSE (SocialAgent) instanciado com iris-fast:latest.", AGENT_ID)
    return agent
