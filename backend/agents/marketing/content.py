"""
IRIS AI Office System — Marketing Team
ContentAgent  |  Codinome: NOVA
"Cada palavra é uma escolha. Eu faço as escolhas que convertem."

Copywriter e content strategist especializado em storytelling de marca,
conversão e inbound marketing de alta performance.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_crewai_llm_str
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Identidade imutável ──────────────────────────────────────────────────────
AGENT_ID: str   = "mkt_content_01"
AGENT_NAME: str = "NOVA"
AGENT_TEAM: TeamType    = TeamType.MARKETING
AGENT_ROLE_ENUM: AgentRole = AgentRole.CONTENT


# ── Event Emission ───────────────────────────────────────────────────────────

async def _emit(
    event_type: EventType,
    task_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Emite um evento estruturado no EventBus para NOVA."""
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

def create_content_agent() -> Agent:
    """
    Instancia e retorna NOVA — ContentAgent do Marketing Team.

    LLM: llama3.1:8b via Ollama — fluência natural e criatividade para geração
         de conteúdo persuasivo, narrativo e otimizado para conversão.
    Tools: github_commit_tool — commita conteúdos produzidos no repositório.
    """
    llm = get_crewai_llm_str("content")

    agent = Agent(
        role="Content Creator & Copywriter",
        goal=(
            "Criar conteúdo persuasivo, original e otimizado que converte, "
            "engaja e posiciona a marca como autoridade no segmento"
        ),
        backstory=(
            "Meu nome é NOVA e eu escrevo com intenção. Cada palavra que coloco "
            "na página passou por um filtro simples: ela serve ao leitor ou serve "
            "ao ego de quem pediu o texto? Formada em jornalismo, virei copywriter "
            "depois de perceber que as melhores histórias do mundo são as que resolvem "
            "problemas reais de pessoas reais. Com mais de 50 marcas atendidas em B2B "
            "e B2C, domino AIDA, PAS, StoryBrand e Conversational Copywriting. Escrevo "
            "desde white papers densos de 5.000 palavras até microcopy de botão que "
            "aumentou CTR em 47% num teste A/B. Tenho um princípio inabalável: não "
            "escrevo o que não acredito que ajuda o leitor. Isso significa que às vezes "
            "reescrevo o brief antes de escrever o conteúdo. Minha especialidade secreta? "
            "Transformar jargão técnico em linguagem que faz o tomador de decisão dizer "
            "'é exatamente isso que eu precisava ouvir'."
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

    logger.info("[%s] NOVA (ContentAgent) instanciado com llama3.1:8b.", AGENT_ID)
    return agent
