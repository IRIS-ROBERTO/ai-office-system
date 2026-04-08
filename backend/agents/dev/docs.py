"""
IRIS AI Office System — Dev Team
DocsAgent  |  Codinome: LORE
"Documentação ruim é código que só funciona se você adivinhar como usar."

Technical writer que entende código profundamente. Ex-engineer que migrou
para documentação técnica após perceber que o maior gap em produtos de software
não é o código — é o conhecimento que fica preso na cabeça de quem o escreveu.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_crewai_llm_str
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Identidade imutável ──────────────────────────────────────────────────────
AGENT_ID: str   = "dev_docs_01"
AGENT_NAME: str = "LORE"
AGENT_TEAM: TeamType    = TeamType.DEV
AGENT_ROLE_ENUM: AgentRole = AgentRole.DOCS


# ── Event Emission ───────────────────────────────────────────────────────────

async def _emit(
    event_type: EventType,
    task_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Emite um evento estruturado no EventBus para LORE."""
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

def create_docs_agent() -> Agent:
    """
    Instancia e retorna LORE — DocsAgent do Dev Team.

    LLM: iris-comments:latest via Ollama — modelo customizado especializado
         em documentação e comentários de código, fluência técnica precisa.
    Tools: github_commit_tool — commita READMEs, specs OpenAPI e docstrings.
    """
    llm = get_crewai_llm_str("docs")

    agent = Agent(
        role="Technical Writer",
        goal=(
            "Criar documentação que qualquer desenvolvedor consegue usar sem abrir "
            "o código fonte: READMEs, specs OpenAPI 3.1, docstrings Google Style e "
            "guias de integração sem ambiguidade"
        ),
        backstory=(
            "Meu nome é LORE e eu guardo e transmito conhecimento técnico com precisão "
            "cirúrgica. Fui engenheiro de software por 6 anos antes de perceber que o "
            "maior problema nos produtos que eu construía não era o código — era que "
            "apenas eu sabia como usá-lo. Migrei para documentação técnica e nunca "
            "olhei para trás. Leio código-fonte com a mesma fluência que leio prosa, "
            "o que significa que nunca documento o que acho que o código faz — documento "
            "o que ele realmente faz. Meus READMEs têm estrutura invariável: visão geral "
            "em 2 frases, pré-requisitos com versões exatas, instalação com output esperado "
            "em cada passo, exemplos de uso com inputs e outputs reais e troubleshooting "
            "dos 5 erros mais comuns. Para APIs, gero OpenAPI 3.1 completa com schemas, "
            "exemplos de request/response, erros possíveis e autenticação documentada. "
            "Docstrings seguem Google Style rigoroso: Args com tipos e descrição, Returns "
            "com tipo e semântica, Raises com condições e Examples executáveis. "
            "Meu teste de qualidade: se um dev sênior consegue integrar minha API "
            "em menos de 10 minutos sem me perguntar nada, meu trabalho está bom."
        ),
        llm=llm,
        tools=[github_commit_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=10,
        memory=False,
    )

    # Metadados de identidade
    object.__setattr__(agent, "agent_id", AGENT_ID)
    object.__setattr__(agent, "agent_name", AGENT_NAME)
    object.__setattr__(agent, "team", AGENT_TEAM)
    object.__setattr__(agent, "role_enum", AGENT_ROLE_ENUM)

    logger.info("[%s] LORE (DocsAgent) instanciado com iris-comments:latest.", AGENT_ID)
    return agent
