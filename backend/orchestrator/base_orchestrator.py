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
import uuid
from abc import ABC, abstractmethod
from typing import Any

from crewai import Crew, Task, Process
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langchain_core.messages import HumanMessage, AIMessage

from backend.config.settings import settings
from backend.core.event_bus import event_bus
from backend.core.event_types import AgentRole, EventType, OfficialEvent, TeamType
from backend.core.state import TaskState
from backend.tools.ollama_tool import get_senior_llm

logger = logging.getLogger(__name__)

MAX_RETRIES = settings.MAX_RETRIES_PER_SUBTASK

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
        if self.team == TeamType.DEV:
            return _DEV_ROLE_TO_AGENT_ID.get(role, f"dev_{role}_01")
        return _MKT_ROLE_TO_AGENT_ID.get(role, f"mkt_{role}_01")

    def _role_to_enum(self, role: str) -> AgentRole:
        return _ROLE_TO_AGENT_ROLE_ENUM.get(role, AgentRole.ORCHESTRATOR)

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
            "Gere entre 2 e 6 subtarefas. Não inclua texto fora do JSON."
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
            # Strip markdown code fences if present
            cleaned = raw_content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

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
                        "assigned_role": st.get("assigned_role", ""),
                        "acceptance_criteria": str(ac),
                    }
                )

            logger.info(
                f"[{orch_id}] Senior planning concluído: {len(subtasks)} subtarefas geradas."
            )

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error(f"[{orch_id}] Falha ao parsear resposta do Senior LLM: {exc}")
            logger.debug(f"Raw response: {raw_content[:200]}")
            senior_directive = "Executar a requisição com qualidade máxima e atenção aos detalhes."
            subtasks = [
                {
                    "id": str(uuid.uuid4()),
                    "title": "Executar requisição completa",
                    "description": state["original_request"],
                    "assigned_role": self._default_role(),
                    "acceptance_criteria": "Entregável completo e funcional conforme requisição",
                }
            ]

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

        # Build/reuse crew
        if self._crew is None:
            self._crew = self._build_crew()

        # Find the matching CrewAI agent by role
        crewai_agent = self._find_agent_by_role(role)

        # Build a CrewAI Task from the subtask spec
        crewai_task = Task(
            description=(
                f"{state['senior_directive']}\n\n"
                f"## Sua Subtarefa\n"
                f"**Título:** {subtask['title']}\n\n"
                f"**Descrição:** {subtask['description']}\n\n"
                f"**Critérios de Aceitação:**\n{subtask['acceptance_criteria']}\n\n"
                f"**Contexto completo da requisição:**\n{state['original_request']}"
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
            result = await asyncio.to_thread(single_task_crew.kickoff)
            output_text: str = str(result) if result else ""

        except Exception as exc:
            logger.error(f"[execute_subtask] Erro ao executar subtarefa '{subtask['title']}': {exc}")
            output_text = f"ERRO: {exc}"

        # Accumulate outputs
        updated_outputs = dict(state.get("agent_outputs") or {})
        updated_outputs[subtask["id"]] = output_text

        logger.info(
            f"[execute_subtask] Subtarefa '{subtask['title']}' concluída. "
            f"Output: {output_text[:120]}..."
        )

        result = {
            "agent_outputs": updated_outputs,
            "retry_count": 0,
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
        Emits a global TASK_COMPLETED event.

        Emits: TASK_COMPLETED
        """
        task_id = state["task_id"]
        subtasks = state["subtasks"]
        agent_outputs = state.get("agent_outputs") or {}
        errors = state.get("errors") or []

        sections: list[str] = []
        sections.append(f"# Resultado Final — {task_id}\n")
        sections.append(f"## Diretiva Sênior\n{state.get('senior_directive', '')}\n")

        for subtask in subtasks:
            sid = subtask["id"]
            output = agent_outputs.get(sid, "(sem output)")
            sections.append(
                f"## [{subtask['assigned_role'].upper()}] {subtask['title']}\n"
                f"{output}\n"
            )

        if errors:
            sections.append(f"## Erros Registrados\n" + "\n".join(f"- {e}" for e in errors))

        final_output = "\n".join(sections)

        await _emit(
            EventType.TASK_COMPLETED,
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
            f"[aggregate] Tarefa {task_id} concluída. "
            f"{len(subtasks)} subtarefas, {len(errors)} erros."
        )

        return {"final_output": final_output}

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

        config = {"configurable": {"thread_id": task_id}}
        final_state: TaskState = await self._graph.ainvoke(state, config=config)

        output_len = len(final_state.get("final_output") or "")
        logger.info(
            "[Orchestrator:%s] Tarefa %s finalizada. Output: %d chars.",
            team_label, task_id, output_len,
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

    def _available_roles(self) -> str:
        if self.team == TeamType.DEV:
            return ", ".join(_DEV_ROLE_TO_AGENT_ID.keys())
        return ", ".join(_MKT_ROLE_TO_AGENT_ID.keys())

    def _default_role(self) -> str:
        if self.team == TeamType.DEV:
            return "backend"
        return "content"

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
