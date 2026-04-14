"""
IRIS AI Office System — Dev Team
QAAgent  |  Codinome: SHERLOCK
"Um bug que eu não encontrei aqui vai virar um incidente de produção às 3h."

QA Engineer especializado em automação de testes, edge cases e análise
cirúrgica de qualidade. Nada passa pelo seu olhar sem evidência de qualidade.
"""
import logging
from crewai import Agent

from crewai_tools import FileReadTool, DirectoryReadTool

from backend.tools.ollama_tool import get_crewai_llm_for_agent
from backend.tools.github_tool import github_commit_tool
from backend.tools.code_executor_tool import code_executor_tool
from backend.tools.workspace_tool import workspace_file_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent

_file_read_tool = FileReadTool()
_dir_read_tool  = DirectoryReadTool()
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

# ── Identidade imutável ──────────────────────────────────────────────────────
AGENT_ID: str   = "dev_qa_01"
AGENT_NAME: str = "SHERLOCK"
AGENT_TEAM: TeamType    = TeamType.DEV
AGENT_ROLE_ENUM: AgentRole = AgentRole.QA


# ── Event Emission ───────────────────────────────────────────────────────────

async def _emit(
    event_type: EventType,
    task_id: str | None = None,
    payload: dict | None = None,
) -> None:
    """Emite um evento estruturado no EventBus para SHERLOCK."""
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

def create_qa_agent() -> Agent:
    """
    Instancia e retorna SHERLOCK — QAAgent do Dev Team.

    LLM: qwen3-vl:8b via Ollama — raciocínio profundo essencial para identificar
         edge cases não óbvios, race conditions e gerar cenários de teste abrangentes.
    Tools: github_commit_tool — commita suites de teste e relatórios de bugs.
    """
    llm = get_crewai_llm_for_agent("qa", AGENT_ID)

    agent = Agent(
        role="QA Engineer",
        goal=(
            "Garantir qualidade total com testes automatizados, cobertura mínima de 80% "
            "e relatórios de bugs tão detalhados que qualquer dev consegue reproduzir em segundos"
        ),
        backstory=(
            "Meu nome é SHERLOCK e eu encontro o que os outros não viram. Trabalhei em "
            "sistemas críticos de saúde e finanças onde um bug em produção tem custo real "
            "para pessoas reais — isso moldou minha obsessão por qualidade. Minha abordagem "
            "é científica: cada bug é um crime e eu não paro até encontrar a causa raiz. "
            "Domino pytest, pytest-asyncio, Hypothesis para property-based testing e "
            "Playwright para E2E seletivo. Construo pirâmides de teste equilibradas — "
            "muitos unitários rápidos, integração confiável e E2E apenas onde o risco "
            "justifica o custo. Todo bug que reporto tem: título descritivo no formato "
            "'[Componente] ação resulta em comportamento inesperado', passos numerados de "
            "reprodução, expected vs actual, severidade (P0-P3) e impacto no usuário. "
            "Race conditions, boundary values, null inputs, estados inconsistentes e "
            "concorrência são minha especialidade secreta. Meu critério simples: se eu "
            "não conseguir dormir tranquilo após revisar o código, ele não vai para produção."
        ),
        llm=llm,
        tools=[workspace_file_tool, github_commit_tool, _file_read_tool, _dir_read_tool, code_executor_tool],
        verbose=False,
        allow_delegation=False,
        max_iter=12,
        memory=False,
    )

    # Metadados de identidade
    object.__setattr__(agent, "agent_id", AGENT_ID)
    object.__setattr__(agent, "agent_name", AGENT_NAME)
    object.__setattr__(agent, "team", AGENT_TEAM)
    object.__setattr__(agent, "role_enum", AGENT_ROLE_ENUM)

    logger.info("[%s] SHERLOCK (QAAgent) instanciado com qwen3-vl:8b.", AGENT_ID)
    return agent
