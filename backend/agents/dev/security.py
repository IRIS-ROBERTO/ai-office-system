"""
AI Office System — Dev Team: SecurityAgent
Especialista em segurança de aplicações web e APIs, responsável por auditar
cada entregável contra o OWASP Top 10 antes de qualquer merge.
"""
import logging
from crewai import Agent

from backend.tools.ollama_tool import get_reasoning_llm
from backend.core.event_types import AgentRole, TeamType, EventType, OfficialEvent
from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)

AGENT_ID: str = "dev_security_01"
AGENT_TEAM: TeamType = TeamType.DEV
AGENT_ROLE_ENUM: AgentRole = AgentRole.SECURITY


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


def create_security_agent() -> Agent:
    """
    Instancia e retorna o SecurityAgent configurado para o Dev Team.

    LLM: DeepSeek R1 via Ollama (get_reasoning_llm) — raciocínio profundo
         necessário para análise de fluxos de ataque e threat modeling.
    Tools: [] — auditoria é análise pura; sem ferramentas externas para
           evitar vazamento de código sensível para APIs de terceiros.
    """
    llm = get_reasoning_llm()

    agent = Agent(
        role="Security Engineer",
        goal=(
            "Identificar e corrigir vulnerabilidades seguindo OWASP Top 10 "
            "antes de qualquer entrega"
        ),
        backstory=(
            "Especialista em segurança de aplicações web e APIs. "
            "Possui experiência em penetration testing de plataformas SaaS, "
            "condução de threat modeling com STRIDE e implementação de pipelines "
            "de SAST/DAST em CI/CD. Conhece de memória o OWASP Top 10, CWE/SANS Top 25 "
            "e boas práticas do NIST Cybersecurity Framework. "
            "Revisa cada endpoint buscando: injeção (SQL, NoSQL, command), "
            "broken authentication, exposição de dados sensíveis, XXE, "
            "misconfigurações de segurança, XSS, deserialização insegura, "
            "dependências com CVEs conhecidos e logging insuficiente. "
            "Para cada vulnerabilidade encontrada entrega: severidade (CVSS), "
            "vetor de ataque, prova de conceito e remediação exata com código corrigido. "
            "Nenhum código vai para produção sem seu visto de aprovação."
        ),
        llm=llm,
        tools=[],  # Auditoria pura — sem tools externas intencionalmente
        verbose=True,
        allow_delegation=False,
        max_iter=10,
        memory=True,
    )

    agent.agent_id = AGENT_ID          # type: ignore[attr-defined]
    agent.team = AGENT_TEAM            # type: ignore[attr-defined]
    agent.role_enum = AGENT_ROLE_ENUM  # type: ignore[attr-defined]

    logger.info(f"[{AGENT_ID}] SecurityAgent instanciado com DeepSeek R1.")
    return agent
