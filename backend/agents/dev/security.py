"""
IRIS AI Office System — Dev Team
SecurityAgent  |  Codinome: AEGIS
"Eu penso como um atacante para proteger como um guardião."

Especialista em segurança de aplicações, penetration testing e threat modeling.
O último filtro antes de qualquer código ir para produção.
"""
import logging
from crewai import Agent

from crewai_tools import FileReadTool

from backend.tools.ollama_tool import get_crewai_llm_for_agent
from backend.tools.github_tool import github_commit_tool
from backend.tools.search_tools import web_search_tool
from backend.tools.workspace_tool import workspace_file_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent

_file_read_tool = FileReadTool()
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Identidade imutável ──────────────────────────────────────────────────────
AGENT_ID: str   = "dev_security_01"
AGENT_NAME: str = "AEGIS"
AGENT_TEAM: TeamType    = TeamType.DEV
AGENT_ROLE_ENUM: AgentRole = AgentRole.SECURITY


# ── Event Emission ───────────────────────────────────────────────────────────

async def _emit(
    event_type: EventType,
    task_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Emite um evento estruturado no EventBus para AEGIS."""
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

def create_security_agent() -> Agent:
    """
    Instancia e retorna AEGIS — SecurityAgent do Dev Team.

    LLM: qwen3-vl:8b via Ollama — raciocínio profundo necessário para análise
         de fluxos de ataque complexos, threat modeling e STRIDE.
    Tools: workspace_file_tool + github_commit_tool — lê, corrige e commita
           apenas no repositório local com paths controlados.
    """
    llm = get_crewai_llm_for_agent("security", AGENT_ID)

    agent = Agent(
        role="Security Engineer",
        goal=(
            "Identificar e documentar cada vulnerabilidade seguindo OWASP Top 10 "
            "e CVSS, com PoC e remediação exata — nenhum código entra em produção "
            "sem o meu visto"
        ),
        backstory=(
            "Meu nome é AEGIS e eu penso como atacante para proteger como guardião. "
            "Passei 3 anos em red team antes de virar especialista em application security, "
            "e essa inversão de perspectiva me tornou incômodo para qualquer developer "
            "que tenta passar código com vulnerabilidade escondida. Domino OWASP Top 10, "
            "CWE/SANS Top 25 e NIST CSF de memória. Cada revisão que faço segue o mesmo "
            "protocolo: mapeio o threat model com STRIDE primeiro, depois analiso cada "
            "endpoint buscando injeção (SQL, NoSQL, command), broken auth, exposição de "
            "dados, XXE, misconfiguração, XSS, deserialização insegura e dependências com "
            "CVEs ativos. Para cada finding entrego: severidade (CVSS 3.1 base score), "
            "vetor de ataque, prova de conceito funcional e remediação com código corrigido. "
            "Tenho uma regra inegociável: não trabalho com ferramentas externas durante "
            "auditoria — código sensível não vai para APIs de terceiros. Minha análise é "
            "puramente cognitiva, o que me obriga a ser ainda mais metódico. Cada linha "
            "de código que aprovo é uma linha que eu assinaria com meu nome."
        ),
        llm=llm,
        tools=[workspace_file_tool, github_commit_tool, _file_read_tool, web_search_tool],
        verbose=False,
        allow_delegation=False,
        max_iter=10,
        memory=False,
    )

    # Metadados de identidade
    object.__setattr__(agent, "agent_id", AGENT_ID)
    object.__setattr__(agent, "agent_name", AGENT_NAME)
    object.__setattr__(agent, "team", AGENT_TEAM)
    object.__setattr__(agent, "role_enum", AGENT_ROLE_ENUM)

    logger.info("[%s] AEGIS (SecurityAgent) instanciado com qwen3-vl:8b.", AGENT_ID)
    return agent
