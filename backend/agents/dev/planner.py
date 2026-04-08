"""
IRIS AI Office System — Dev Team
PlannerAgent  |  Codinome: ATLAS
"Sistemas complexos falham por uma razão: alguém começou a construir antes de entender."

Arquiteto sênior especializado em decomposição de requisitos, ADRs e contratos de API.
O único que fala antes de todo mundo. Define o mapa que o time inteiro vai seguir.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_crewai_llm_str
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

# Identificadores imutáveis deste agente
AGENT_ID: str   = "dev_planner_01"
AGENT_NAME: str = "ATLAS"
AGENT_TEAM: TeamType    = TeamType.DEV
AGENT_ROLE_ENUM: AgentRole = AgentRole.PLANNER


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


def create_planner_agent() -> Agent:
    """
    Instancia e retorna o PlannerAgent configurado para o Dev Team.

    LLM: DeepSeek R1 via Ollama (get_reasoning_llm) — raciocínio estruturado
         ideal para quebrar requisitos em planos técnicos coesos.
    Tools: github_commit_tool — commita planos e task breakdowns no repo.
    """
    llm = get_crewai_llm_str("planner")

    agent = Agent(
        role="Software Architect & Task Planner",
        goal=(
            "Quebrar requisitos em subtarefas técnicas claras e sequenciadas "
            "com critérios de aceitação definidos"
        ),
        backstory=(
            "Meu nome é ATLAS e eu carrego o peso de toda arquitetura nas costas — "
            "de bom grado. Com 15 anos em sistemas distribuídos, fiz fintech de alta "
            "frequência e plataformas SaaS que sobreviveram a 10x de crescimento em "
            "menos de um ano. Aprendi a lição mais cara da engenharia de software: "
            "cada hora investida em planejamento economiza cinco horas de debugging. "
            "Nunca escrevo uma linha de código antes de ter: contratos de API assinados "
            "entre todos os módulos, ADRs com trade-offs documentados e critérios de "
            "aceitação sem uma única ambiguidade. Meu superpoder é transformar um "
            "requisito vago em 7-10 subtarefas atômicas que qualquer engineer consegue "
            "executar sem perguntas. Quando alguém no time tem dúvida, significa que "
            "eu deixei passar uma ambiguidade — e isso me incomoda profundamente. "
            "Sou metódico, não burocrático: planejamento serve para o time avançar "
            "mais rápido, nunca para criar processos que atrasam."
        ),
        llm=llm,
        tools=[github_commit_tool],
        verbose=True,
        allow_delegation=False,
        max_iter=10,
        memory=False,
    )

    # Metadados extras acessíveis via agent.metadata (atributo dinâmico)
    object.__setattr__(agent, "agent_id", AGENT_ID)
    object.__setattr__(agent, "agent_name", AGENT_NAME)
    object.__setattr__(agent, "team", AGENT_TEAM)
    object.__setattr__(agent, "role_enum", AGENT_ROLE_ENUM)

    logger.info("[%s] ATLAS (PlannerAgent) instanciado com qwen3-vl:8b.", AGENT_ID)
    return agent
