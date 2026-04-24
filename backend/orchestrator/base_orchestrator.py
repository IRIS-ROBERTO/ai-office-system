"""
AI Office System — BaseOrchestrator
LangGraph StateGraph orchestrator that coordinates CrewAI agents through a
senior-planning → routing → execution → quality-gate → aggregation pipeline.

All nodes emit OfficialEvent instances to the EventBus so the Visual Engine
and frontend receive real-time state updates.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from abc import ABC, abstractmethod
from typing import Any

from crewai import Agent, Crew, Task, Process
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langchain_core.messages import HumanMessage, AIMessage

from backend.config.settings import settings
from backend.core.delivery_evidence import validate_delivery_evidence
from backend.core.delivery_runner import delivery_runner
from backend.core.event_bus import event_bus
from backend.core.execution_trace import append_execution_log
from backend.core.event_types import AgentRole, EventType, OfficialEvent, TeamType
from backend.core.gold_standard import GENERATED_PROJECTS_ROOT, REPO_ROOT, build_gold_standard_prompt
from backend.core.improvement_loop import improvement_loop
from backend.core.static_web_delivery import (
    can_handle_complex_project_delivery,
    can_handle_static_web_delivery,
    execute_complex_project_delivery,
    execute_static_web_delivery,
)
from backend.core.state import TaskState
from backend.tools.brain_router import record_transient_openrouter_failure
from backend.tools.ollama_tool import get_crewai_llm_str, get_senior_llm

logger = logging.getLogger(__name__)

MAX_RETRIES = settings.MAX_RETRIES_PER_SUBTASK


def _is_transient_model_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "429",
            "rate limit",
            "ratelimit",
            "too many requests",
            "high demand",
            "provider error",
            "openrouter",
        )
    )


def _extract_json_object(raw: str) -> str:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        cleaned = cleaned.strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned

# ---------------------------------------------------------------------------
# Role → agent_id look-up tables (one per team)
# ---------------------------------------------------------------------------

_DEV_ROLE_TO_AGENT_ID: dict[str, str] = {
    "planner": "dev_planner_01",
    "frontend": "dev_frontend_01",
    "backend": "dev_backend_01",
    "qa": "dev_qa_01",
    "security": "dev_security_01",
    "docs": "dev_docs_01",
}

_MKT_ROLE_TO_AGENT_ID: dict[str, str] = {
    "research": "mkt_research_01",
    "strategy": "mkt_strategy_01",
    "content": "mkt_content_01",
    "seo": "mkt_seo_01",
    "social": "mkt_social_01",
    "analytics": "mkt_analytics_01",
}

_ROLE_TO_AGENT_ROLE_ENUM: dict[str, AgentRole] = {
    "planner": AgentRole.PLANNER,
    "frontend": AgentRole.FRONTEND,
    "backend": AgentRole.BACKEND,
    "qa": AgentRole.QA,
    "security": AgentRole.SECURITY,
    "docs": AgentRole.DOCS,
    "research": AgentRole.RESEARCH,
    "strategy": AgentRole.STRATEGY,
    "content": AgentRole.CONTENT,
    "seo": AgentRole.SEO,
    "social": AgentRole.SOCIAL,
    "analytics": AgentRole.ANALYTICS,
}


# ---------------------------------------------------------------------------
# Helper — fire-and-forget event emission (safe inside sync node wrappers)
# ---------------------------------------------------------------------------

async def _emit(
    event_type: EventType,
    team: TeamType,
    agent_id: str,
    agent_role: AgentRole,
    task_id: str | None = None,
    payload: dict | None = None,
) -> None:
    event = OfficialEvent(
        event_type=event_type,
        team=team,
        agent_id=agent_id,
        agent_role=agent_role,
        task_id=task_id,
        payload=payload or {},
    )
    try:
        await event_bus.emit(event)
    except Exception as exc:
        logger.warning(f"[EventBus] Falha ao emitir {event_type}: {exc}")


# ---------------------------------------------------------------------------
# BaseOrchestrator
# ---------------------------------------------------------------------------

class BaseOrchestrator(ABC):
    """
    Abstract base for all team orchestrators.

    Sub-classes must implement:
        _build_crew()           — returns a configured CrewAI Crew
        _senior_system_context  — extra system context injected into senior LLM
    """

    ORCHESTRATOR_AGENT_ID = "orchestrator_senior_01"

    def __init__(self, team: TeamType) -> None:
        self.team = team
        self._llm = get_senior_llm()
        self._crew: Crew | None = None
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def _senior_system_context(self) -> str:
        """Team-specific context prepended to every senior LLM call."""

    @abstractmethod
    def _build_crew(self) -> Crew:
        """Construct and return the CrewAI Crew for this team."""

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    def _role_to_agent_id(self, role: str) -> str:
        role = self._normalize_role(role)
        if self.team == TeamType.DEV:
            return _DEV_ROLE_TO_AGENT_ID.get(role, f"dev_{role}_01")
        return _MKT_ROLE_TO_AGENT_ID.get(role, f"mkt_{role}_01")

    def _role_to_enum(self, role: str) -> AgentRole:
        role = self._normalize_role(role)
        return _ROLE_TO_AGENT_ROLE_ENUM.get(role, AgentRole.ORCHESTRATOR)

    def _normalize_role(self, role: str | None) -> str:
        normalized = (role or "").strip().lower()
        aliases = {
            "front-end": "frontend",
            "front end": "frontend",
            "ui": "frontend",
            "ux": "frontend",
            "doc": "docs",
            "docos": "docs",
            "documentation": "docs",
            "tester": "qa",
            "quality": "qa",
        }
        normalized = aliases.get(normalized, normalized)
        available = _DEV_ROLE_TO_AGENT_ID if self.team == TeamType.DEV else _MKT_ROLE_TO_AGENT_ID
        return normalized if normalized in available else self._default_role()

    def _trace(
        self,
        task_id: str,
        stage: str,
        message: str,
        *,
        level: str = "info",
        agent_id: str | None = None,
        agent_role: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        append_execution_log(
            task_id=task_id,
            team=self.team.value,
            stage=stage,
            message=message,
            level=level,
            agent_id=agent_id,
            agent_role=agent_role,
            metadata=metadata,
        )
        line = "[Trace][%s][%s][%s/%s] %s" % (
            task_id[:8],
            stage,
            agent_role or "system",
            agent_id or "n/a",
            message,
        )
        if level == "error":
            logger.error(line)
        elif level == "warning":
            logger.warning(line)
        else:
            logger.info(line)

    async def _emit_execution_heartbeat(
        self,
        task_id: str,
        subtask: dict,
        agent_id: str,
        agent_role_enum: AgentRole,
    ) -> None:
        elapsed = 0
        while True:
            await asyncio.sleep(settings.EXECUTION_HEARTBEAT_SECONDS)
            elapsed += settings.EXECUTION_HEARTBEAT_SECONDS
            await _emit(
                EventType.TASK_HEARTBEAT,
                self.team,
                agent_id,
                agent_role_enum,
                task_id=task_id,
                payload={
                    "subtask_id": subtask["id"],
                    "subtask_title": subtask["title"],
                    "elapsed_seconds": elapsed,
                },
            )
            self._trace(
                task_id,
                "subtask_heartbeat",
                f"Subtarefa '{subtask['title']}' segue em execucao ha {elapsed}s.",
                agent_id=agent_id,
                agent_role=agent_role_enum.value,
                metadata={"subtask_id": subtask["id"], "elapsed_seconds": elapsed},
            )

    # ------------------------------------------------------------------
    # LangGraph node: senior_planning_node
    # ------------------------------------------------------------------

    async def _senior_planning_node(self, state: TaskState) -> dict:
        """
        Calls the Senior LLM (Claude Sonnet via OpenRouter) to:
          1. Produce a `senior_directive` — high-level strategic guidance.
          2. Generate a structured list of `subtasks`, each with:
             { id, title, description, assigned_role, acceptance_criteria }

        Emits: AGENT_CALLED, AGENT_THINKING
        """
        task_id = state["task_id"]
        orch_id = self.ORCHESTRATOR_AGENT_ID

        await _emit(
            EventType.AGENT_CALLED,
            self.team,
            orch_id,
            AgentRole.ORCHESTRATOR,
            task_id=task_id,
            payload={"request": state["original_request"]},
        )
        await _emit(
            EventType.AGENT_THINKING,
            self.team,
            orch_id,
            AgentRole.ORCHESTRATOR,
            task_id=task_id,
            payload={"context": "Analisando requisição e decompondo em subtarefas"},
        )
        self._trace(
            task_id,
            "senior_planning_start",
            "Orquestrador iniciou a decomposicao da solicitacao.",
            agent_id=orch_id,
            agent_role=AgentRole.ORCHESTRATOR.value,
        )

        if self._wants_atomic_subtask(state["original_request"]):
            senior_directive = (
                "Executar a solicitação como entrega atômica: um único agente deve produzir "
                "os arquivos reais, validar objetivamente, commitar localmente e retornar "
                "DELIVERY_EVIDENCE completo. Não dividir em fases, não delegar planejamento "
                "separado e não encerrar sem commit verificável."
            )
            subtasks = self._fallback_subtasks_for_request(state["original_request"])
            self._trace(
                task_id,
                "senior_planning_complete",
                "Planejamento atomico aplicado com 1 subtarefa.",
                agent_id=orch_id,
                agent_role=AgentRole.ORCHESTRATOR.value,
                metadata={"subtask_count": len(subtasks), "mode": "atomic_override"},
            )
            result = {
                "senior_directive": senior_directive,
                "subtasks": subtasks,
                "current_subtask_index": 0,
                "messages": [
                    HumanMessage(content=state["original_request"]),
                    AIMessage(content=senior_directive),
                ],
            }
            self._report_progress({**state, **result})
            return result

        if self._wants_gold_standard_project_pipeline(state["original_request"]):
            senior_directive = (
                "Executar como projeto completo em pipeline padrão ouro. O orquestrador deve "
                "garantir participação sequencial de planner, frontend, backend, qa, security "
                "e docs. Cada especialista deve produzir arquivos reais, validar objetivamente, "
                "criar commit local próprio e retornar DELIVERY_EVIDENCE verificável. O projeto "
                "só pode ser agregado quando todos os manifestos obrigatórios estiverem aprovados."
            )
            subtasks = self._gold_standard_project_subtasks(state["original_request"])
            self._trace(
                task_id,
                "senior_planning_complete",
                f"Pipeline padrao ouro aplicado com {len(subtasks)} especialistas.",
                agent_id=orch_id,
                agent_role=AgentRole.ORCHESTRATOR.value,
                metadata={"subtask_count": len(subtasks), "mode": "gold_standard_project_pipeline"},
            )
            result = {
                "senior_directive": senior_directive,
                "subtasks": subtasks,
                "current_subtask_index": 0,
                "messages": [
                    HumanMessage(content=state["original_request"]),
                    AIMessage(content=senior_directive),
                ],
            }
            self._report_progress({**state, **result})
            return result

        system_prompt = (
            f"{self._senior_system_context}\n\n"
            "Você é o Orquestrador Sênior do AI Office System.\n"
            "Analise a requisição a seguir e:\n"
            "1. Escreva uma diretiva estratégica clara (senior_directive) em 2-3 parágrafos.\n"
            "2. Decomponha o trabalho em subtarefas sequenciais.\n\n"
            "Responda EXCLUSIVAMENTE com um objeto JSON válido no formato:\n"
            "{\n"
            '  "senior_directive": "<texto da diretiva>",\n'
            '  "subtasks": [\n'
            "    {\n"
            '      "id": "<uuid>",\n'
            '      "title": "<título conciso>",\n'
            '      "description": "<descrição detalhada do que deve ser feito>",\n'
            '      "assigned_role": "<role do agente responsável>",\n'
            '      "acceptance_criteria": "<critérios mensuráveis de conclusão>"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"Roles disponíveis: {self._available_roles()}\n"
            "Regra de roteamento: assigned_role deve conter exatamente UM role disponível, "
            "sem vírgulas e sem múltiplos responsáveis. Se houver colaboração, crie subtarefas separadas.\n"
            "Cada subtarefa versionável deve incluir nos critérios: alteração real via workspace_file, "
            "validação objetiva, commit local via github_commit e DELIVERY_EVIDENCE com SHA real.\n"
            "Gere entre 1 e 6 subtarefas. Se a requisição pedir tarefa atomica/simples, "
            "crie uma única subtarefa com o role mais adequado. Não inclua texto fora do JSON."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["original_request"]},
        ]

        # Retry logic: on RateLimitError fall back to local Ollama automatically
        from backend.tools.ollama_tool import get_local_llm
        from backend.config.settings import settings as _settings
        _llm_candidates = [self._llm]
        # Always have a local fallback available
        _llm_candidates.append(get_local_llm(model=_settings.LOCAL_MODEL_CODE, temperature=0.2))
        _llm_candidates.append(get_local_llm(model=_settings.LOCAL_MODEL_FALLBACK, temperature=0.2))

        raw_content: str = ""
        last_exc: Exception | None = None

        for _llm_attempt in _llm_candidates:
            try:
                response = await _llm_attempt.ainvoke(messages)
                raw_content = response.content if hasattr(response, "content") else str(response)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()
                if "429" in err_str or "rate" in err_str or "quota" in err_str:
                    record_transient_openrouter_failure(str(getattr(_llm_attempt, "model", "?")), exc)
                    logger.warning(
                        "[%s] RateLimit/Quota em %s — tentando proximo modelo. Erro: %s",
                        orch_id, getattr(_llm_attempt, 'model', '?'), exc
                    )
                    continue
                # Non-rate-limit error — don't retry
                logger.error("[%s] Erro nao-RateLimit no LLM: %s", orch_id, exc)
                break

        if last_exc and not raw_content:
            logger.error(f"[{orch_id}] Todos os LLMs falharam: {last_exc}")
            raw_content = ""

        try:
            cleaned = _extract_json_object(raw_content)
            parsed: dict = json.loads(cleaned)
            senior_directive: str = parsed.get("senior_directive", "")
            raw_subtasks: list[dict] = parsed.get("subtasks", [])

            # Ensure every subtask has a unique id
            subtasks: list[dict] = []
            for st in raw_subtasks:
                # acceptance_criteria pode vir como lista do LLM → normalizar para string
                ac = st.get("acceptance_criteria", "")
                if isinstance(ac, list):
                    ac = "\n".join(f"- {item}" for item in ac)
                subtasks.append(
                    {
                        "id": st.get("id") or str(uuid.uuid4()),
                        "title": st.get("title", "Subtarefa"),
                        "description": st.get("description", ""),
                        "assigned_role": self._normalize_role(st.get("assigned_role", "")),
                        "acceptance_criteria": str(ac),
                    }
                )

            logger.info(
                f"[{orch_id}] Senior planning concluído: {len(subtasks)} subtarefas geradas."
            )
            self._trace(
                task_id,
                "senior_planning_complete",
                f"Planejamento concluido com {len(subtasks)} subtarefas.",
                agent_id=orch_id,
                agent_role=AgentRole.ORCHESTRATOR.value,
                metadata={"subtask_count": len(subtasks)},
            )

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error(f"[{orch_id}] Falha ao parsear resposta do Senior LLM: {exc}")
            logger.debug(f"Raw response: {raw_content[:200]}")
            self._trace(
                task_id,
                "senior_planning_fallback",
                f"Falha ao parsear JSON do planejamento; fallback para subtarefa unica. Erro: {exc}",
                level="warning",
                agent_id=orch_id,
                agent_role=AgentRole.ORCHESTRATOR.value,
            )
            senior_directive = "Executar a requisição com qualidade máxima e atenção aos detalhes."
            subtasks = self._fallback_subtasks_for_request(state["original_request"])

        result = {
            "senior_directive": senior_directive,
            "subtasks": subtasks,
            "current_subtask_index": 0,
            "messages": [
                HumanMessage(content=state["original_request"]),
                AIMessage(content=senior_directive),
            ],
        }
        # Merge and report intermediate progress
        merged = {**state, **result}
        self._report_progress(merged)
        return result

    # ------------------------------------------------------------------
    # LangGraph node: route_to_agent_node
    # ------------------------------------------------------------------

    async def _route_to_agent_node(self, state: TaskState) -> dict:
        """
        Reads the current subtask and emits AGENT_ASSIGNED to the
        responsible agent so the Visual Engine can animate movement.

        Emits: AGENT_ASSIGNED
        """
        idx = state["current_subtask_index"]
        subtasks = state["subtasks"]

        if idx >= len(subtasks):
            logger.warning("[route_to_agent_node] Índice fora dos limites — nenhuma subtarefa.")
            return {}

        subtask = subtasks[idx]
        role: str = subtask.get("assigned_role", self._default_role())
        agent_id = self._role_to_agent_id(role)
        agent_role_enum = self._role_to_enum(role)

        await _emit(
            EventType.AGENT_ASSIGNED,
            self.team,
            agent_id,
            agent_role_enum,
            task_id=state["task_id"],
            payload={
                "subtask_id": subtask["id"],
                "subtask_title": subtask["title"],
                "subtask_index": idx,
                "total_subtasks": len(subtasks),
            },
        )

        logger.info(
            f"[route_to_agent] Subtarefa [{idx + 1}/{len(subtasks)}] "
            f"'{subtask['title']}' → {agent_id}"
        )
        self._trace(
            state["task_id"],
            "agent_routed",
            f"Subtarefa '{subtask['title']}' roteada para {role}.",
            agent_id=agent_id,
            agent_role=agent_role_enum.value,
            metadata={"subtask_id": subtask["id"], "subtask_index": idx},
        )
        return {}

    # ------------------------------------------------------------------
    # LangGraph node: execute_subtask_node
    # ------------------------------------------------------------------

    async def _execute_subtask_node(self, state: TaskState) -> dict:
        """
        Executes the current subtask via CrewAI.
        Lazily initialises the Crew on first call.

        Emits: TASK_STARTED, TASK_IN_PROGRESS
        """
        idx = state["current_subtask_index"]
        subtasks = state["subtasks"]
        subtask = subtasks[idx]
        task_id = state["task_id"]

        role: str = subtask.get("assigned_role", self._default_role())
        agent_id = self._role_to_agent_id(role)
        agent_role_enum = self._role_to_enum(role)

        await _emit(
            EventType.TASK_STARTED,
            self.team,
            agent_id,
            agent_role_enum,
            task_id=task_id,
            payload={
                "subtask_id": subtask["id"],
                "subtask_title": subtask["title"],
                "retry_count": state["retry_count"],
            },
        )

        await _emit(
            EventType.TASK_IN_PROGRESS,
            self.team,
            agent_id,
            agent_role_enum,
            task_id=task_id,
            payload={
                "subtask_id": subtask["id"],
                "description": subtask["description"],
                "acceptance_criteria": subtask["acceptance_criteria"],
            },
        )
        self._trace(
            task_id,
            "subtask_start",
            f"Agente {role} iniciou a subtarefa '{subtask['title']}'.",
            agent_id=agent_id,
            agent_role=agent_role_enum.value,
            metadata={"subtask_id": subtask["id"], "retry_count": state["retry_count"]},
        )

        if can_handle_complex_project_delivery(subtask):
            try:
                output_text = execute_complex_project_delivery(
                    task_id=task_id,
                    subtask_id=subtask["id"],
                    agent_id=agent_id,
                    agent_role=agent_role_enum.value,
                    subtask=subtask,
                )
                self._trace(
                    task_id,
                    "deterministic_executor",
                    f"Executor deterministico entregou artefatos do especialista {role}.",
                    agent_id=agent_id,
                    agent_role=agent_role_enum.value,
                    metadata={"subtask_id": subtask["id"]},
                )
            except Exception as exc:
                output_text = f"ERRO: executor deterministico de projeto completo falhou: {exc}"
                self._trace(
                    task_id,
                    "deterministic_executor_failed",
                    f"Executor deterministico de projeto completo falhou: {exc}",
                    level="error",
                    agent_id=agent_id,
                    agent_role=agent_role_enum.value,
                    metadata={"subtask_id": subtask["id"]},
                )

            updated_outputs = dict(state.get("agent_outputs") or {})
            updated_outputs[subtask["id"]] = output_text
            updated_evidence = dict(state.get("delivery_evidence") or {})
            updated_manifests = dict(state.get("delivery_manifests") or {})

            manifest = delivery_runner.evaluate_subtask_output(
                task_id=task_id,
                subtask=subtask,
                output_text=output_text,
                agent_id=agent_id,
                agent_role=agent_role_enum.value,
                team=self.team.value,
                require_commit=self._subtask_requires_commit(subtask),
            )
            updated_manifests[subtask["id"]] = manifest.to_dict()
            self._trace(
                task_id,
                "delivery_manifest",
                f"Delivery Runner avaliou '{subtask['title']}' com approved={manifest.approved}.",
                agent_id=self.ORCHESTRATOR_AGENT_ID,
                agent_role=AgentRole.ORCHESTRATOR.value,
                metadata={
                    "subtask_id": subtask["id"],
                    "approved": manifest.approved,
                    "manifest_path": manifest.manifest_path,
                    "failed_stages": [
                        stage.name for stage in manifest.stages if stage.required and not stage.passed
                    ],
                },
            )

            evidence_payload = dict(manifest.evidence or {})
            if evidence_payload:
                evidence_payload["approved"] = manifest.approved
                evidence_payload["feedback"] = manifest.feedback
                evidence_payload["manifest_path"] = manifest.manifest_path
                updated_evidence[subtask["id"]] = evidence_payload

                commit_sha = str(evidence_payload.get("commit_sha") or "")
                if manifest.approved and commit_sha:
                    await _emit(
                        EventType.GIT_COMMIT,
                        self.team,
                        agent_id,
                        agent_role_enum,
                        task_id=task_id,
                        payload={
                            "subtask_id": subtask["id"],
                            "sha": commit_sha,
                            "message": evidence_payload.get("commit_message"),
                            "files": evidence_payload.get("files_changed"),
                            "pushed": evidence_payload.get("pushed"),
                            "manifest_path": manifest.manifest_path,
                        },
                    )

            self._trace(
                task_id,
                "subtask_complete",
                f"Subtarefa '{subtask['title']}' encerrou execucao.",
                agent_id=agent_id,
                agent_role=agent_role_enum.value,
                metadata={"subtask_id": subtask["id"], "output_preview": output_text[:120]},
            )
            result = {
                "agent_outputs": updated_outputs,
                "delivery_evidence": updated_evidence,
                "delivery_manifests": updated_manifests,
            }
            self._report_progress({**state, **result})
            return result

        if can_handle_static_web_delivery(subtask):
            try:
                output_text = execute_static_web_delivery(
                    task_id=task_id,
                    subtask_id=subtask["id"],
                    agent_id=agent_id,
                    subtask=subtask,
                )
                self._trace(
                    task_id,
                    "deterministic_executor",
                    "Executor deterministico frontend entregou projeto web estatico.",
                    agent_id=agent_id,
                    agent_role=agent_role_enum.value,
                    metadata={"subtask_id": subtask["id"]},
                )
            except Exception as exc:
                output_text = f"ERRO: executor deterministico frontend falhou: {exc}"
                self._trace(
                    task_id,
                    "deterministic_executor_failed",
                    f"Executor deterministico frontend falhou: {exc}",
                    level="error",
                    agent_id=agent_id,
                    agent_role=agent_role_enum.value,
                    metadata={"subtask_id": subtask["id"]},
                )

            updated_outputs = dict(state.get("agent_outputs") or {})
            updated_outputs[subtask["id"]] = output_text
            updated_evidence = dict(state.get("delivery_evidence") or {})
            updated_manifests = dict(state.get("delivery_manifests") or {})

            manifest = delivery_runner.evaluate_subtask_output(
                task_id=task_id,
                subtask=subtask,
                output_text=output_text,
                agent_id=agent_id,
                agent_role=agent_role_enum.value,
                team=self.team.value,
                require_commit=self._subtask_requires_commit(subtask),
            )
            updated_manifests[subtask["id"]] = manifest.to_dict()
            self._trace(
                task_id,
                "delivery_manifest",
                f"Delivery Runner avaliou '{subtask['title']}' com approved={manifest.approved}.",
                agent_id=self.ORCHESTRATOR_AGENT_ID,
                agent_role=AgentRole.ORCHESTRATOR.value,
                metadata={
                    "subtask_id": subtask["id"],
                    "approved": manifest.approved,
                    "manifest_path": manifest.manifest_path,
                    "failed_stages": [
                        stage.name for stage in manifest.stages if stage.required and not stage.passed
                    ],
                },
            )

            evidence_payload = dict(manifest.evidence or {})
            if evidence_payload:
                evidence_payload["approved"] = manifest.approved
                evidence_payload["feedback"] = manifest.feedback
                evidence_payload["manifest_path"] = manifest.manifest_path
                updated_evidence[subtask["id"]] = evidence_payload

                commit_sha = str(evidence_payload.get("commit_sha") or "")
                if manifest.approved and commit_sha:
                    await _emit(
                        EventType.GIT_COMMIT,
                        self.team,
                        agent_id,
                        agent_role_enum,
                        task_id=task_id,
                        payload={
                            "subtask_id": subtask["id"],
                            "sha": commit_sha,
                            "message": evidence_payload.get("commit_message"),
                            "files": evidence_payload.get("files_changed"),
                            "pushed": evidence_payload.get("pushed"),
                            "manifest_path": manifest.manifest_path,
                        },
                    )

            self._trace(
                task_id,
                "subtask_complete",
                f"Subtarefa '{subtask['title']}' encerrou execucao.",
                agent_id=agent_id,
                agent_role=agent_role_enum.value,
                metadata={"subtask_id": subtask["id"], "output_preview": output_text[:120]},
            )
            result = {
                "agent_outputs": updated_outputs,
                "delivery_evidence": updated_evidence,
                "delivery_manifests": updated_manifests,
            }
            self._report_progress({**state, **result})
            return result

        # Build/reuse crew
        if self._crew is None:
            self._crew = self._build_crew()

        # Find the matching CrewAI agent by role
        crewai_agent = self._find_agent_by_role(role)

        # Build a CrewAI Task from the subtask spec
        retry_feedback = (state.get("agent_outputs") or {}).get(f"{subtask['id']}_feedback", "")
        retry_section = (
            "\n\n## Feedback obrigatorio da tentativa anterior\n"
            f"{retry_feedback}\n"
            "Corrija exatamente estes pontos antes de responder novamente.\n"
            if retry_feedback
            else ""
        )
        crewai_task = Task(
            description=(
                f"{state['senior_directive']}\n\n"
                f"## Sua Subtarefa\n"
                f"**Título:** {subtask['title']}\n\n"
                f"**Descrição:** {subtask['description']}\n\n"
                f"**Critérios de Aceitação:**\n{subtask['acceptance_criteria']}\n\n"
                f"**Contexto completo da requisição:**\n{state['original_request']}\n\n"
                f"{retry_section}"
                f"{self._role_hardening_contract(role)}"
                f"{build_gold_standard_prompt(role=role, agent_id=agent_id)}\n\n"
                "## Regra obrigatória de versionamento\n"
                "Se você produzir qualquer artefato versionável (código, documentação, teste, "
                "conteúdo ou configuração), deve usar a tool `github_commit` em modo local "
                "com `repo_path`, `file_paths` e `commit_message` para fazer git add e git commit "
                "no repositório local.\n"
                f"Use repo_path='{REPO_ROOT}' para alterar o IRIS. Para projeto gerado, use a raiz git/worktree criada dentro de '{GENERATED_PROJECTS_ROOT}'. Use push=false se o remoto não estiver disponível.\n"
                "Nunca conclua a subtarefa sem evidência explícita do commit real retornado pela tool.\n"
                "No seu output final, inclua exatamente este bloco parseável:\n"
                "DELIVERY_EVIDENCE\n"
                f"agent: {agent_id}\n"
                f"task_id: {task_id}\n"
                f"subtask_id: {subtask['id']}\n"
                "repo_path: caminho_absoluto_do_repositorio_git_usado\n"
                "files_changed:\n"
                "- path/do/arquivo\n"
                "validation:\n"
                "- command: comando executado\n"
                "  result: passed|failed|not_applicable\n"
                "commit:\n"
                "  message: mensagem do commit\n"
                "  sha: sha_curto\n"
                "  pushed: true|false\n"
                "risks:\n"
                "- none\n"
                "next_handoff: none\n"
            ),
            expected_output=subtask["acceptance_criteria"],
            agent=crewai_agent,
        )

        try:
            # CrewAI kickoff() é SÍNCRONO — roda em thread para não bloquear o event loop
            single_task_crew = Crew(
                agents=[crewai_agent],
                tasks=[crewai_task],
                process=Process.sequential,
                verbose=False,
            )
            heartbeat_task = asyncio.create_task(
                self._emit_execution_heartbeat(task_id, subtask, agent_id, agent_role_enum)
            )
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(single_task_crew.kickoff),
                    timeout=settings.SUBTASK_EXECUTION_TIMEOUT_SECONDS,
                )
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            output_text: str = str(result) if result else ""

        except asyncio.TimeoutError:
            timeout_s = settings.SUBTASK_EXECUTION_TIMEOUT_SECONDS
            output_text = f"ERRO: subtarefa excedeu timeout de {timeout_s}s."
            self._trace(
                task_id,
                "subtask_timeout",
                f"Subtarefa '{subtask['title']}' excedeu o timeout de {timeout_s}s.",
                level="error",
                agent_id=agent_id,
                agent_role=agent_role_enum.value,
                metadata={"subtask_id": subtask["id"], "timeout_seconds": timeout_s},
            )
        except Exception as exc:
            if _is_transient_model_error(exc):
                record_transient_openrouter_failure(str(getattr(crewai_agent, "llm", "unknown")), exc)
                fallback_llm = get_crewai_llm_str(role)
                logger.warning(
                    "[execute_subtask] Modelo remoto falhou para '%s'; fallback local %s. Erro: %s",
                    subtask["title"],
                    fallback_llm,
                    exc,
                )
                self._trace(
                    task_id,
                    "model_fallback",
                    f"Modelo remoto indisponivel/rate limited; fallback local aplicado: {fallback_llm}.",
                    level="warning",
                    agent_id=agent_id,
                    agent_role=agent_role_enum.value,
                    metadata={"subtask_id": subtask["id"], "fallback_llm": fallback_llm},
                )
                try:
                    fallback_agent = Agent(
                        role=crewai_agent.role,
                        goal=crewai_agent.goal,
                        backstory=crewai_agent.backstory,
                        llm=fallback_llm,
                        tools=list(crewai_agent.tools or []),
                        verbose=False,
                        allow_delegation=False,
                        max_iter=settings.MAX_RETRIES_PER_SUBTASK * 3,
                        memory=False,
                    )
                    object.__setattr__(fallback_agent, "agent_id", agent_id)
                    object.__setattr__(fallback_agent, "agent_name", getattr(crewai_agent, "agent_name", agent_id))
                    object.__setattr__(fallback_agent, "team", self.team)
                    object.__setattr__(fallback_agent, "role_enum", agent_role_enum)
                    fallback_task = Task(
                        description=crewai_task.description,
                        expected_output=crewai_task.expected_output,
                        agent=fallback_agent,
                    )
                    fallback_crew = Crew(
                        agents=[fallback_agent],
                        tasks=[fallback_task],
                        process=Process.sequential,
                        verbose=False,
                    )
                    heartbeat_task = asyncio.create_task(
                        self._emit_execution_heartbeat(task_id, subtask, agent_id, agent_role_enum)
                    )
                    try:
                        result = await asyncio.wait_for(
                            asyncio.to_thread(fallback_crew.kickoff),
                            timeout=settings.SUBTASK_EXECUTION_TIMEOUT_SECONDS,
                        )
                    finally:
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass
                    output_text = str(result) if result else ""
                except Exception as fallback_exc:
                    logger.error(
                        "[execute_subtask] Fallback local tambem falhou para '%s': %s",
                        subtask["title"],
                        fallback_exc,
                    )
                    output_text = f"ERRO: remoto falhou ({exc}); fallback local falhou ({fallback_exc})"
                    self._trace(
                        task_id,
                        "subtask_error",
                        f"Fallback local falhou para '{subtask['title']}': {fallback_exc}",
                        level="error",
                        agent_id=agent_id,
                        agent_role=agent_role_enum.value,
                        metadata={"subtask_id": subtask["id"]},
                    )
            else:
                logger.error(f"[execute_subtask] Erro ao executar subtarefa '{subtask['title']}': {exc}")
                output_text = f"ERRO: {exc}"
                self._trace(
                    task_id,
                    "subtask_error",
                    f"Erro ao executar subtarefa '{subtask['title']}': {exc}",
                    level="error",
                    agent_id=agent_id,
                    agent_role=agent_role_enum.value,
                    metadata={"subtask_id": subtask["id"]},
                )

        # Accumulate outputs
        updated_outputs = dict(state.get("agent_outputs") or {})
        updated_outputs[subtask["id"]] = output_text
        updated_evidence = dict(state.get("delivery_evidence") or {})
        updated_manifests = dict(state.get("delivery_manifests") or {})

        manifest = delivery_runner.evaluate_subtask_output(
            task_id=task_id,
            subtask=subtask,
            output_text=output_text,
            agent_id=agent_id,
            agent_role=agent_role_enum.value,
            team=self.team.value,
            require_commit=self._subtask_requires_commit(subtask),
        )
        updated_manifests[subtask["id"]] = manifest.to_dict()
        self._trace(
            task_id,
            "delivery_manifest",
            f"Delivery Runner avaliou '{subtask['title']}' com approved={manifest.approved}.",
            agent_id=self.ORCHESTRATOR_AGENT_ID,
            agent_role=AgentRole.ORCHESTRATOR.value,
            metadata={
                "subtask_id": subtask["id"],
                "approved": manifest.approved,
                "manifest_path": manifest.manifest_path,
                "failed_stages": [
                    stage.name for stage in manifest.stages if stage.required and not stage.passed
                ],
            },
        )

        evidence_payload = dict(manifest.evidence or {})
        if evidence_payload:
            evidence_payload["approved"] = manifest.approved
            evidence_payload["feedback"] = manifest.feedback
            evidence_payload["manifest_path"] = manifest.manifest_path
            updated_evidence[subtask["id"]] = evidence_payload

            commit_sha = str(evidence_payload.get("commit_sha") or "")
            if manifest.approved and commit_sha:
                await _emit(
                    EventType.GIT_COMMIT,
                    self.team,
                    agent_id,
                    agent_role_enum,
                    task_id=task_id,
                    payload={
                        "subtask_id": subtask["id"],
                        "sha": commit_sha,
                        "message": evidence_payload.get("commit_message"),
                        "files": evidence_payload.get("files_changed"),
                        "pushed": evidence_payload.get("pushed"),
                        "manifest_path": manifest.manifest_path,
                    },
                )
                if evidence_payload.get("pushed"):
                    await _emit(
                        EventType.GIT_PUSH,
                        self.team,
                        agent_id,
                        agent_role_enum,
                        task_id=task_id,
                        payload={
                            "subtask_id": subtask["id"],
                            "sha": commit_sha,
                            "files": evidence_payload.get("files_changed"),
                            "manifest_path": manifest.manifest_path,
                        },
                    )
        else:
            await _emit(
                EventType.COMMIT_FAILED,
                self.team,
                agent_id,
                agent_role_enum,
                task_id=task_id,
                payload={
                    "subtask_id": subtask["id"],
                    "reason": manifest.feedback,
                    "manifest_path": manifest.manifest_path,
                },
            )

        logger.info(
            f"[execute_subtask] Subtarefa '{subtask['title']}' concluída. "
            f"Output: {output_text[:120]}..."
        )
        self._trace(
            task_id,
            "subtask_complete",
            f"Subtarefa '{subtask['title']}' encerrou execucao.",
            agent_id=agent_id,
            agent_role=agent_role_enum.value,
            metadata={"subtask_id": subtask["id"], "output_preview": output_text[:120]},
        )

        result = {
            "agent_outputs": updated_outputs,
            "delivery_evidence": updated_evidence,
            "delivery_manifests": updated_manifests,
        }
        # Report progress after each subtask completion
        merged = {**state, **result}
        self._report_progress(merged)
        return result

    # ------------------------------------------------------------------
    # LangGraph node: quality_gate_node
    # ------------------------------------------------------------------

    async def _quality_gate_node(self, state: TaskState) -> dict:
        """
        Calls the Senior LLM to evaluate whether the latest subtask output
        satisfies its acceptance criteria.

        Emits: TASK_COMPLETED (approved) or TASK_FAILED (rejected after max retries)
        """
        idx = state["current_subtask_index"]
        subtask = state["subtasks"][idx]
        task_id = state["task_id"]
        agent_outputs = state.get("agent_outputs") or {}
        output_text = agent_outputs.get(subtask["id"], "")

        role: str = subtask.get("assigned_role", self._default_role())
        agent_id = self._role_to_agent_id(role)
        agent_role_enum = self._role_to_enum(role)

        manifest_payload = (state.get("delivery_manifests") or {}).get(subtask["id"]) or {}
        if manifest_payload.get("approved") is True:
            self._trace(
                task_id,
                "quality_gate_result",
                f"Delivery Runner aprovou '{subtask['title']}'; quality gate deterministico aceito.",
                agent_id=self.ORCHESTRATOR_AGENT_ID,
                agent_role=AgentRole.ORCHESTRATOR.value,
                metadata={
                    "subtask_id": subtask["id"],
                    "approved": True,
                    "source": "delivery_runner",
                    "manifest_path": manifest_payload.get("manifest_path"),
                },
            )
            await _emit(
                EventType.TASK_COMPLETED,
                self.team,
                agent_id,
                agent_role_enum,
                task_id=task_id,
                payload={
                    "subtask_id": subtask["id"],
                    "approved": True,
                    "feedback": manifest_payload.get("feedback", "Delivery Runner approved."),
                    "manifest_path": manifest_payload.get("manifest_path"),
                },
            )
            return {
                "quality_approved": True,
                "current_subtask_index": idx,
            }

        if manifest_payload.get("approved") is False:
            feedback = str(manifest_payload.get("feedback") or "Delivery Runner reprovou a entrega.")
            retry_count = state.get("retry_count", 0) + 1
            updated_outputs = dict(agent_outputs)
            updated_outputs[f"{subtask['id']}_feedback"] = feedback
            self._trace(
                task_id,
                "deterministic_gate_failed",
                f"Manifesto deterministico reprovou '{subtask['title']}': {feedback}",
                level="warning",
                agent_id=agent_id,
                agent_role=agent_role_enum.value,
                metadata={
                    "subtask_id": subtask["id"],
                    "retry_count": retry_count,
                    "manifest_path": manifest_payload.get("manifest_path"),
                },
            )

            if retry_count >= MAX_RETRIES:
                errors = list(state.get("errors") or [])
                errors.append(
                    f"Subtarefa '{subtask['title']}' reprovada pelo manifesto deterministico "
                    f"apos {MAX_RETRIES} tentativas. Ultimo feedback: {feedback}"
                )
                await _emit(
                    EventType.TASK_FAILED,
                    self.team,
                    agent_id,
                    agent_role_enum,
                    task_id=task_id,
                    payload={
                        "subtask_id": subtask["id"],
                        "feedback": feedback,
                        "retry_count": retry_count,
                        "manifest_path": manifest_payload.get("manifest_path"),
                    },
                )
                return {
                    "quality_approved": False,
                    "retry_count": retry_count,
                    "agent_outputs": updated_outputs,
                    "errors": errors,
                    "current_subtask_index": idx,
                }

            return {
                "quality_approved": False,
                "retry_count": retry_count,
                "agent_outputs": updated_outputs,
                "current_subtask_index": idx,
            }

        deterministic_gate = validate_delivery_evidence(
            output_text,
            task_id=task_id,
            subtask_id=subtask["id"],
            require_commit=self._subtask_requires_commit(subtask),
        )
        if not deterministic_gate.approved:
            retry_count = state.get("retry_count", 0) + 1
            updated_outputs = dict(agent_outputs)
            updated_outputs[f"{subtask['id']}_feedback"] = deterministic_gate.feedback
            updated_evidence = dict(state.get("delivery_evidence") or {})
            if deterministic_gate.evidence:
                payload = deterministic_gate.evidence.to_dict()
                payload["approved"] = False
                payload["feedback"] = deterministic_gate.feedback
                updated_evidence[subtask["id"]] = payload

            self._trace(
                task_id,
                "deterministic_gate_failed",
                f"Evidencia deterministica reprovou '{subtask['title']}': {deterministic_gate.feedback}",
                level="warning",
                agent_id=agent_id,
                agent_role=agent_role_enum.value,
                metadata={"subtask_id": subtask["id"], "retry_count": retry_count},
            )

            if retry_count >= MAX_RETRIES:
                errors = list(state.get("errors") or [])
                errors.append(
                    f"Subtarefa '{subtask['title']}' reprovada por falta de evidência após "
                    f"{MAX_RETRIES} tentativas. Último feedback: {deterministic_gate.feedback}"
                )
                await _emit(
                    EventType.TASK_FAILED,
                    self.team,
                    agent_id,
                    agent_role_enum,
                    task_id=task_id,
                    payload={
                        "subtask_id": subtask["id"],
                        "feedback": deterministic_gate.feedback,
                        "retry_count": retry_count,
                    },
                )
                return {
                    "quality_approved": False,
                    "retry_count": retry_count,
                    "agent_outputs": updated_outputs,
                    "delivery_evidence": updated_evidence,
                    "errors": errors,
                    "current_subtask_index": idx,
                }

            return {
                "quality_approved": False,
                "retry_count": retry_count,
                "agent_outputs": updated_outputs,
                "delivery_evidence": updated_evidence,
                "current_subtask_index": idx,
            }

        if not settings.QUALITY_GATE_ENABLED:
            logger.info("[quality_gate] Gate desabilitado — aprovação automática.")
            await _emit(
                EventType.TASK_COMPLETED,
                self.team,
                agent_id,
                agent_role_enum,
                task_id=task_id,
                payload={"subtask_id": subtask["id"], "approved": True},
            )
            return {
                "quality_approved": True,
                "current_subtask_index": idx,
            }

        evaluation_prompt = (
            f"{self._senior_system_context}\n\n"
            "Você é o Orquestrador Sênior avaliando a qualidade de um entregável.\n\n"
            f"**Subtarefa:** {subtask['title']}\n"
            f"**Critérios de Aceitação:** {subtask['acceptance_criteria']}\n\n"
            f"**Output produzido pelo agente:**\n{output_text}\n\n"
            "Regra adicional obrigatória: se a subtarefa gera artefatos versionáveis, o output "
            "precisa conter evidência explícita de commit (arquivos alterados + mensagem + SHA "
            "ou saída da tool github_commit). Se não houver essa evidência, aprove como false.\n\n"
            "Avalie se o output atende COMPLETAMENTE os critérios de aceitação.\n"
            "Responda APENAS com JSON válido:\n"
            '{"approved": true, "feedback": "..."}\n'
            "ou\n"
            '{"approved": false, "feedback": "<o que está faltando ou incorreto>"}'
        )

        messages = [
            {"role": "system", "content": evaluation_prompt},
            {"role": "user", "content": f"Avalie o output acima para a subtarefa '{subtask['title']}'."},
        ]

        approved = False
        feedback = ""

        try:
            response = await self._llm.ainvoke(messages)
            raw: str = response.content if hasattr(response, "content") else str(response)
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

            parsed = json.loads(cleaned)
            approved = bool(parsed.get("approved", False))
            feedback = parsed.get("feedback", "")

        except Exception as exc:
            logger.warning(f"[quality_gate] Erro ao parsear resposta LLM: {exc} — fallback conservador.")
            approved = False
            feedback = (
                "Quality gate não conseguiu validar o output por falha de parser. "
                "Refine o entregável e responda em JSON válido."
            )

        logger.info(
            f"[quality_gate] Subtarefa '{subtask['title']}' — "
            f"approved={approved}, feedback={feedback[:80]}"
        )
        self._trace(
            task_id,
            "quality_gate_result",
            f"Quality gate avaliou '{subtask['title']}' com approved={approved}.",
            agent_id=self.ORCHESTRATOR_AGENT_ID,
            agent_role=AgentRole.ORCHESTRATOR.value,
            metadata={"subtask_id": subtask["id"], "approved": approved, "feedback": feedback[:240]},
        )

        if approved:
            await _emit(
                EventType.TASK_COMPLETED,
                self.team,
                agent_id,
                agent_role_enum,
                task_id=task_id,
                payload={
                    "subtask_id": subtask["id"],
                    "approved": True,
                    "feedback": feedback,
                },
            )
            return {
                "quality_approved": True,
                "current_subtask_index": idx,
            }

        # Not approved
        retry_count = state.get("retry_count", 0) + 1

        if retry_count >= MAX_RETRIES:
            logger.warning(
                f"[quality_gate] Subtarefa '{subtask['title']}' falhou após {retry_count} tentativas."
            )
            self._trace(
                task_id,
                "quality_gate_failed",
                f"Subtarefa '{subtask['title']}' reprovada definitivamente apos {retry_count} tentativas.",
                level="error",
                agent_id=self.ORCHESTRATOR_AGENT_ID,
                agent_role=AgentRole.ORCHESTRATOR.value,
                metadata={"subtask_id": subtask["id"], "retry_count": retry_count},
            )
            errors = list(state.get("errors") or [])
            errors.append(
                f"Subtarefa '{subtask['title']}' não aprovada após {MAX_RETRIES} tentativas. "
                f"Último feedback: {feedback}"
            )
            await _emit(
                EventType.TASK_FAILED,
                self.team,
                agent_id,
                agent_role_enum,
                task_id=task_id,
                payload={
                    "subtask_id": subtask["id"],
                    "feedback": feedback,
                    "retry_count": retry_count,
                },
            )
            return {
                "quality_approved": False,
                "retry_count": retry_count,
                "errors": errors,
                "current_subtask_index": idx,
            }

        # Retry: inject feedback into agent_outputs so the next execute picks it up
        updated_outputs = dict(agent_outputs)
        updated_outputs[f"{subtask['id']}_feedback"] = feedback

        logger.info(
            f"[quality_gate] Retry {retry_count}/{MAX_RETRIES} para '{subtask['title']}'."
        )
        self._trace(
            task_id,
            "quality_gate_retry",
            f"Subtarefa '{subtask['title']}' precisa de nova tentativa ({retry_count}/{MAX_RETRIES}).",
            level="warning",
            agent_id=self.ORCHESTRATOR_AGENT_ID,
            agent_role=AgentRole.ORCHESTRATOR.value,
            metadata={"subtask_id": subtask["id"], "retry_count": retry_count},
        )
        return {
            "quality_approved": False,
            "retry_count": retry_count,
            "agent_outputs": updated_outputs,
            "current_subtask_index": idx,
        }

    # ------------------------------------------------------------------
    # LangGraph node: aggregate_results_node
    # ------------------------------------------------------------------

    async def _aggregate_results_node(self, state: TaskState) -> dict:
        """
        Aggregates all agent_outputs into a final_output string.
        Emits a global TASK_COMPLETED event when clean, or TASK_FAILED when any
        deterministic/quality gate errors were collected.

        Emits: TASK_COMPLETED or TASK_FAILED
        """
        task_id = state["task_id"]
        subtasks = state["subtasks"]
        agent_outputs = state.get("agent_outputs") or {}
        delivery_evidence = state.get("delivery_evidence") or {}
        delivery_manifests = state.get("delivery_manifests") or {}
        errors = state.get("errors") or []

        sections: list[str] = []
        sections.append(f"# Resultado Final — {task_id}\n")
        sections.append(f"## Diretiva Sênior\n{state.get('senior_directive', '')}\n")

        for subtask in subtasks:
            sid = subtask["id"]
            output = agent_outputs.get(sid, "(sem output)")
            evidence = delivery_evidence.get(sid)
            sections.append(
                f"## [{subtask['assigned_role'].upper()}] {subtask['title']}\n"
                f"{output}\n"
            )
            if evidence:
                sections.append(
                    "### Delivery Evidence\n"
                    f"- Commit: {evidence.get('commit_sha') or 'n/a'}\n"
                    f"- Pushed: {evidence.get('pushed')}\n"
                    f"- Files: {', '.join(evidence.get('files_changed') or []) or 'n/a'}\n"
                    f"- Gate: {evidence.get('feedback') or 'n/a'}\n"
                    f"- Manifest: {evidence.get('manifest_path') or 'n/a'}\n"
                )
            manifest = delivery_manifests.get(sid)
            if manifest:
                failed_stages = [
                    item.get("name")
                    for item in manifest.get("stages", [])
                    if item.get("required") and item.get("status") != "passed"
                ]
                sections.append(
                    "### Delivery Manifest\n"
                    f"- Approved: {manifest.get('approved')}\n"
                    f"- Path: {manifest.get('manifest_path') or 'n/a'}\n"
                    f"- Failed stages: {', '.join(failed_stages) if failed_stages else 'none'}\n"
                )

        if errors:
            sections.append(f"## Erros Registrados\n" + "\n".join(f"- {e}" for e in errors))

        final_output = "\n".join(sections)

        final_event_type = EventType.TASK_FAILED if errors else EventType.TASK_COMPLETED
        await _emit(
            final_event_type,
            self.team,
            self.ORCHESTRATOR_AGENT_ID,
            AgentRole.ORCHESTRATOR,
            task_id=task_id,
            payload={
                "subtask_count": len(subtasks),
                "error_count": len(errors),
                "output_length": len(final_output),
            },
        )

        logger.info(
            f"[aggregate] Tarefa {task_id} agregada. "
            f"{len(subtasks)} subtarefas, {len(errors)} erros."
        )
        self._trace(
            task_id,
            "aggregation_complete",
            f"Tarefa agregada pelo orquestrador com {len(subtasks)} subtarefas e {len(errors)} erros.",
            level="error" if errors else "info",
            agent_id=self.ORCHESTRATOR_AGENT_ID,
            agent_role=AgentRole.ORCHESTRATOR.value,
            metadata={"subtask_count": len(subtasks), "error_count": len(errors)},
        )

        # Fire improvement loop as background task — doesn't block the response
        asyncio.create_task(
            self._run_improvement_loop(state, task_id, subtasks, agent_outputs)
        )

        return {"final_output": final_output}

    async def _run_improvement_loop(
        self,
        state: TaskState,
        task_id: str,
        subtasks: list[dict],
        agent_outputs: dict,
    ) -> None:
        """
        Coleta auto-análise de cada agente e sintetiza proposals de melhoria.
        Roda em background para não bloquear a entrega do resultado ao usuário.
        """
        from backend.tools.ollama_tool import get_local_llm
        from backend.config.settings import settings as _s

        analyses = []
        agent_llm = get_local_llm(model=_s.LOCAL_MODEL_FALLBACK, temperature=0.2)

        for subtask in subtasks:
            sid = subtask["id"]
            role = subtask.get("assigned_role", self._default_role())
            agent_id = self._role_to_agent_id(role)
            output_text = agent_outputs.get(sid, "")
            if not output_text:
                continue
            try:
                analysis = await improvement_loop.collect_agent_analysis(
                    agent_id=agent_id,
                    agent_role=role,
                    task_id=task_id,
                    task_output=output_text,
                    llm=agent_llm,
                )
                analyses.append(analysis)
            except Exception as exc:
                logger.warning("[ImprovementLoop] Análise falhou para %s: %s", agent_id, exc)

        if analyses:
            proposals = await improvement_loop.synthesize_proposals(analyses, self._llm)
            await improvement_loop.save_to_supabase(analyses, proposals)
            logger.info(
                "[ImprovementLoop] %d proposals geradas para tarefa %s.",
                len(proposals), task_id,
            )

    # ------------------------------------------------------------------
    # Conditional edge functions
    # ------------------------------------------------------------------

    def _after_quality_gate(self, state: TaskState) -> str:
        """
        Routes after quality_gate_node:
          approved  → next_subtask_or_aggregate
          retry     → execute_subtask
          failed    → aggregate_results  (max retries exceeded)
        """
        idx = state["current_subtask_index"]
        total = len(state["subtasks"])
        approved = state.get("quality_approved", False)
        retry_count = state.get("retry_count", 0)

        if approved:
            if idx + 1 < total:
                return "next_subtask"
            return "aggregate"

        if retry_count >= MAX_RETRIES:
            return "aggregate_with_error"

        return "retry"

    def _after_execute_subtask(self, state: TaskState) -> str:
        """
        Always goes to quality_gate after execution.
        (kept for semantic clarity; unconditional in practice)
        """
        return "quality_gate"

    def _advance_subtask_index(self, state: TaskState) -> dict:
        """Increment current_subtask_index and reset retry counter."""
        return {
            "current_subtask_index": state["current_subtask_index"] + 1,
            "retry_count": 0,
        }

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> Any:
        """Builds and compiles the LangGraph StateGraph."""
        builder = StateGraph(TaskState)

        # Register nodes
        builder.add_node("senior_planning", self._senior_planning_node)
        builder.add_node("route_to_agent", self._route_to_agent_node)
        builder.add_node("execute_subtask", self._execute_subtask_node)
        builder.add_node("quality_gate", self._quality_gate_node)
        builder.add_node("advance_index", self._advance_subtask_index)
        builder.add_node("aggregate_results", self._aggregate_results_node)

        # Entry point
        builder.set_entry_point("senior_planning")

        # Fixed edges
        builder.add_edge("senior_planning", "route_to_agent")
        builder.add_edge("route_to_agent", "execute_subtask")
        builder.add_edge("execute_subtask", "quality_gate")

        # Conditional edge from quality_gate
        builder.add_conditional_edges(
            "quality_gate",
            self._after_quality_gate,
            {
                "next_subtask": "advance_index",
                "aggregate": "aggregate_results",
                "aggregate_with_error": "aggregate_results",
                "retry": "execute_subtask",
            },
        )

        # advance_index loops back to route_to_agent for the next subtask
        builder.add_edge("advance_index", "route_to_agent")

        # Terminal
        builder.add_edge("aggregate_results", END)

        memory = MemorySaver()
        return builder.compile(checkpointer=memory)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        state: TaskState,
        on_progress: Any = None,
    ) -> TaskState:
        """
        Executes the full orchestration pipeline for the given TaskState.

        Args:
            state: Pre-built TaskState with task_id, original_request, team, etc.
            on_progress: Optional callback(state) invoked after each LangGraph
                         node with current intermediate state for real-time
                         status updates to the API layer.

        Returns:
            Final TaskState with senior_directive, subtasks, agent_outputs, final_output.
        """
        task_id = state["task_id"]
        team_label = state.get("team", self.team.value)
        self._on_progress = on_progress

        logger.info(
            "[Orchestrator:%s] Iniciando tarefa %s: '%s...'",
            team_label, task_id, state["original_request"][:80],
        )
        self._trace(
            task_id,
            "orchestrator_run_start",
            "Orquestrador iniciou o grafo de execucao da tarefa.",
            agent_id=self.ORCHESTRATOR_AGENT_ID,
            agent_role=AgentRole.ORCHESTRATOR.value,
        )

        config = {"configurable": {"thread_id": task_id}}
        final_state: TaskState = await self._graph.ainvoke(state, config=config)

        output_len = len(final_state.get("final_output") or "")
        logger.info(
            "[Orchestrator:%s] Tarefa %s finalizada. Output: %d chars.",
            team_label, task_id, output_len,
        )
        self._trace(
            task_id,
            "orchestrator_run_complete",
            f"Grafo de execucao finalizado; output final com {output_len} caracteres.",
            agent_id=self.ORCHESTRATOR_AGENT_ID,
            agent_role=AgentRole.ORCHESTRATOR.value,
        )
        return final_state

    def _report_progress(self, state: TaskState) -> None:
        """Report intermediate progress to API layer via callback."""
        cb = getattr(self, "_on_progress", None)
        if cb is not None:
            try:
                cb(state)
            except Exception as exc:
                logger.debug("Progress callback error: %s", exc)

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------

    def _subtask_requires_commit(self, subtask: dict) -> bool:
        """Versionable work must leave a verifiable local commit, in any team."""
        source = " ".join(
            str(subtask.get(key) or "")
            for key in ("title", "description", "acceptance_criteria", "assigned_role")
        ).lower()

        non_versionable_markers = (
            "not_applicable_commit",
            "sem arquivo",
            "sem artefato",
            "apenas resposta",
            "somente resposta",
            "consulta verbal",
        )
        if any(marker in source for marker in non_versionable_markers):
            return False

        versionable_markers = (
            "arquivo",
            "artefato",
            "documento",
            "relatorio",
            "relatório",
            "planilha",
            "calendario",
            "calendário",
            "copy",
            "brief",
            "campanha",
            "seo",
            "codigo",
            "código",
            "html",
            "api",
            "commit",
            "github_commit",
            "workspace_file",
            "delivery_evidence",
        )
        return self.team.value == "dev" or any(marker in source for marker in versionable_markers)

    def _available_roles(self) -> str:
        if self.team == TeamType.DEV:
            return ", ".join(_DEV_ROLE_TO_AGENT_ID.keys())
        return ", ".join(_MKT_ROLE_TO_AGENT_ID.keys())

    def _default_role(self) -> str:
        if self.team == TeamType.DEV:
            return "backend"
        return "content"

    def _role_hardening_contract(self, role: str) -> str:
        normalized = self._normalize_role(role)
        if normalized == "planner":
            return (
                "## Contrato reforcado do Planner\n"
                "- Nao entregue plano generico.\n"
                "- Liste artefatos e arquivos-alvo explicitamente.\n"
                "- Defina validacao objetiva por frente de trabalho.\n"
                "- Defina handoff explicito entre especialistas.\n"
                "- O plano precisa ser executavel sem interpretacao subjetiva.\n\n"
            )
        if normalized == "research":
            return (
                "## Contrato reforcado de Research\n"
                "- Nao entregue apenas narrativa.\n"
                "- Liste fontes, projetos ou evidencias observadas.\n"
                "- Declare tese principal, risco principal e recomendacao objetiva.\n"
                "- Declare estrategia de entrega: iris_repository ou dedicated_repository.\n"
                "- Se houver artefato versionavel, inclua commit e DELIVERY_EVIDENCE completos.\n\n"
            )
        return ""

    def _wants_gold_standard_project_pipeline(self, request: str) -> bool:
        if self.team != TeamType.DEV:
            return False
        normalized = request.lower()
        markers = (
            "iris_complex_project_delivery",
            "projeto completo",
            "aplicacao completa",
            "aplicação completa",
            "aplicativo completo",
            "cada especialista",
            "multi-agente",
            "multi agente",
            "todos os especialistas",
            "planner, frontend, backend, qa, security",
        )
        return any(marker in normalized for marker in markers)

    def _gold_standard_project_subtasks(self, request: str) -> list[dict]:
        project_slug = self._project_slug_for_request(request)
        project_root = GENERATED_PROJECTS_ROOT / project_slug
        project_instruction = (
            f"{request}\n\n"
            "IRIS_COMPLEX_PROJECT_DELIVERY: usar executor padrao ouro multi-especialista. "
            f"Projeto gerado obrigatorio: {project_root}. "
            "Cada subtarefa deve criar artefatos reais nessa pasta de projeto, validar, commitar "
            "e retornar DELIVERY_EVIDENCE completo."
        )
        role_specs = [
            (
                "planner",
                "Planejar arquitetura, contratos e critérios do projeto",
                "Criar docs/ARCHITECTURE.md, docs/API_CONTRACT.md e project.plan.json com escopo, módulos, critérios e handoffs.",
            ),
            (
                "frontend",
                "Implementar interface corporativa responsiva",
                "Criar index.html, src/styles.css, src/app.js e src/data.js com Command Center, agentes, pipeline e evidência interativa.",
            ),
            (
                "backend",
                "Criar contrato local de dados e API mock",
                "Criar package.json, src/api.js, src/store.js e docs/BACKEND_CONTRACT.md com funções puras verificáveis.",
            ),
            (
                "qa",
                "Validar entrega com smoke test executável",
                "Criar tests/smoke-check.js e docs/QA_REPORT.md validando arquivos, assets e eventos DOM.",
            ),
            (
                "security",
                "Revisar segurança e hardening",
                "Criar security/SECURITY_REVIEW.md e security/headers.json com threat model e headers recomendados.",
            ),
            (
                "docs",
                "Documentar operação e handoff",
                "Criar README.md e docs/RUNBOOK.md com execução local, validação, critérios de promoção e operação.",
            ),
        ]
        return [
            {
                "id": str(uuid.uuid4()),
                "title": title,
                "description": f"{project_instruction}\n\nResponsabilidade do especialista {role}: {description}",
                "assigned_role": role,
                "acceptance_criteria": (
                    f"{description} Validar objetivamente, criar commit local proprio, "
                    f"não usar segredos, manter tudo dentro de {project_root} e responder com DELIVERY_EVIDENCE."
                ),
            }
            for role, title, description in role_specs
        ]

    def _project_slug_for_request(self, request: str) -> str:
        source = request
        title_match = re.search(r"^\s*TITULO:\s*(.+?)\s*$", request, re.IGNORECASE | re.MULTILINE)
        if title_match:
            source = title_match.group(1)
        slug = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")
        slug = slug[:48].strip("-") or "iris-project"
        return f"{slug}-{uuid.uuid4().hex[:8]}"

    def _fallback_subtasks_for_request(self, request: str) -> list[dict]:
        """Deterministic fallback when senior planning returns malformed JSON."""
        normalized = request.lower()
        if self.team == TeamType.DEV:
            if self._wants_gold_standard_project_pipeline(request):
                return self._gold_standard_project_subtasks(request)
            role = self._infer_dev_role_for_request(normalized)
            return [
                {
                    "id": str(uuid.uuid4()),
                    "title": "Implementar entrega principal com evidencias",
                    "description": request,
                    "assigned_role": role,
                    "acceptance_criteria": (
                        "Criar ou alterar arquivos reais via workspace_file, executar validacao objetiva, "
                        "criar commit local via github_commit e responder com DELIVERY_EVIDENCE completo. "
                        "Para entrega web estatica, index.html deve referenciar assets existentes, "
                        "src/app.js deve ser JavaScript vanilla executavel direto no navegador, sem React/JSX "
                        "sem build e sem codigo de teste misturado no runtime."
                    ),
                }
            ]

        return [
            {
                "id": str(uuid.uuid4()),
                "title": "Executar entrega principal com evidencias",
                "description": request,
                "assigned_role": self._default_role(),
                "acceptance_criteria": (
                    "Produzir artefatos reais, registrar validacao objetiva, criar commit local quando "
                    "houver arquivos e responder com DELIVERY_EVIDENCE completo."
                ),
            }
        ]

    def _wants_atomic_subtask(self, request: str) -> bool:
        normalized = request.lower()
        markers = (
            "atomico",
            "atômico",
            "unica subtarefa",
            "única subtarefa",
            "uma unica subtarefa",
            "uma única subtarefa",
            "nao divida",
            "não divida",
            "single subtask",
            "one subtask",
        )
        return any(marker in normalized for marker in markers)

    def _infer_dev_role_for_request(self, normalized_request: str) -> str:
        web_markers = (
            "web",
            "frontend",
            "interface",
            "html",
            "css",
            "javascript",
            "app estatica",
            "app estática",
            "aplicacao web",
            "aplicação web",
            "ui",
            "responsiva",
        )
        if any(marker in normalized_request for marker in web_markers):
            return "frontend"
        return "backend"

    def _find_agent_by_role(self, role: str):
        """
        Finds a CrewAI Agent in self._crew whose role string matches.
        Falls back to the first agent in the crew if no match found.
        """
        if self._crew is None:
            raise RuntimeError("Crew not initialised before _find_agent_by_role call.")

        role_lower = role.lower()
        for agent in self._crew.agents:
            if role_lower in agent.role.lower():
                return agent

        # Fallback: return first agent and warn
        logger.warning(
            f"[_find_agent_by_role] Role '{role}' não encontrado na crew — "
            f"usando '{self._crew.agents[0].role}'."
        )
        return self._crew.agents[0]
