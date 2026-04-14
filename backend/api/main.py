"""
AI Office System — FastAPI Main Application
Entrada HTTP/WebSocket do sistema. Gerencia tarefas, agentes e saúde.
"""
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.core.event_bus import event_bus
from backend.core.execution_trace import (
    append_execution_log,
    get_execution_log,
    get_last_execution_entry,
)
from backend.core.state import TaskState
from backend.core.event_types import AgentRole, EventType, OfficialEvent, TeamType
from backend.core.runtime_registry import agent_registry, seed_agent_registry
from backend.core.improvement_loop import improvement_loop
from backend.core.handoff import create_handoff, get_pending_handoffs, resolve_handoff
from backend.core.agent_personality import get_agent_config, update_agent_config
from backend.core.tool_governance import get_role_tool_policy, list_tool_policies
from backend.config.settings import settings
from backend.tools.brain_router import get_brain_status
from backend.tools.model_gate import gate
from backend.tools.ollama_tool import check_ollama_health
from backend.tools.picoclaw_tool import check_picoclaw_health, get_picoclaw_status
from backend.orchestrator import DevOrchestrator, MarketingOrchestrator
from backend.api.schemas import (
    TaskRequest,
    TaskResponse,
    AgentStatus,
    SystemHealth,
    EventHistoryResponse,
    ServiceRequestCreate,
    ServiceRequestListResponse,
    ServiceRequestResponse,
    ExecutionLogEntryResponse,
    ExecutionLogResponse,
    AgentCapabilities,
    AgentPersonalityConfig,
    AgentPersonalityUpdate,
)
from backend.api.websocket import websocket_endpoint

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estado in-memory: tasks e agentes rastreados em runtime
# ---------------------------------------------------------------------------
_active_tasks: dict[str, TaskState] = {}
_service_requests: dict[str, dict] = {}
_task_to_service_request: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Conecta EventBus + Redis no startup; desconecta no shutdown."""
    logger.info("[Lifespan] Iniciando AI Office System...")
    seed_agent_registry()
    try:
        await event_bus.connect()
        logger.info("[Lifespan] EventBus conectado.")
    except Exception as exc:
        logger.error(f"[Lifespan] Falha ao conectar EventBus: {exc}")

    yield

    logger.info("[Lifespan] Encerrando AI Office System...")
    try:
        await event_bus.disconnect()
        logger.info("[Lifespan] EventBus desconectado.")
    except Exception as exc:
        logger.warning(f"[Lifespan] Erro ao desconectar EventBus: {exc}")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Office System",
    description="Backend do escritório de agentes de IA com orquestração LangGraph.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_task_state(task_id: str, team: str, request: str, priority: int) -> TaskState:
    return TaskState(
        task_id=task_id,
        team=team,
        original_request=request,
        senior_directive=None,
        subtasks=[],
        current_subtask_index=0,
        agent_outputs={},
        delivery_evidence={},
        delivery_manifests={},
        quality_approved=False,
        retry_count=0,
        final_output=None,
        errors=[],
        messages=[],
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _priority_from_urgency(urgency: str) -> int:
    normalized = urgency.lower().strip()
    return {
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }.get(normalized, 2)


def _build_task_prompt(service_request: dict) -> str:
    requester_name = service_request.get("requester_name") or "Solicitante interno"
    requester_team = service_request.get("requester_team") or "Time nao informado"
    due_date = service_request.get("desired_due_date") or "Sem prazo explicito"
    acceptance_criteria = service_request.get("acceptance_criteria") or "Validar a entrega com testes e retorno objetivo."

    return (
        f"TITULO: {service_request['title']}\n"
        f"TIME DESTINO: {service_request['team']}\n"
        f"SOLICITANTE: {requester_name}\n"
        f"AREA SOLICITANTE: {requester_team}\n"
        f"URGENCIA: {service_request['urgency']}\n"
        f"PRAZO DESEJADO: {due_date}\n\n"
        "CONTEXTO DA SOLICITACAO:\n"
        f"{service_request['request']}\n\n"
        "CRITERIOS DE ACEITE:\n"
        f"{acceptance_criteria}\n\n"
        "REQUISITOS OPERACIONAIS:\n"
        "- Registrar a execucao com evidencias claras.\n"
        "- Garantir validacao do time responsavel antes do fechamento.\n"
        "- Encerrar a entrega apenas com aprovacao final do orquestrador.\n"
    )


def _derive_service_request_progress(service_request: dict, task_state: TaskState | None) -> dict:
    if task_state is None:
        return {
            "status": "received",
            "stage_label": "Recebido",
            "current_agent_role": None,
            "tested_by_team": False,
            "approved_by_orchestrator": False,
        }

    subtasks = task_state.get("subtasks") or []
    idx = int(task_state.get("current_subtask_index") or 0)
    current_subtask = subtasks[idx] if 0 <= idx < len(subtasks) else None
    current_role = current_subtask.get("assigned_role") if current_subtask else None
    outputs = task_state.get("agent_outputs") or {}
    errors = task_state.get("errors") or []
    qa_subtasks = [subtask for subtask in subtasks if str(subtask.get("assigned_role", "")).lower() == "qa"]
    tested_by_team = True

    if qa_subtasks:
        tested_by_team = any(outputs.get(subtask["id"]) for subtask in qa_subtasks)
    elif task_state.get("team") == "dev":
        tested_by_team = False

    if errors:
        return {
            "status": "failed",
            "stage_label": "Falha de gate",
            "current_agent_role": current_role or "orchestrator",
            "tested_by_team": tested_by_team,
            "approved_by_orchestrator": False,
        }

    approved_by_orchestrator = bool(task_state.get("final_output"))

    if approved_by_orchestrator:
        return {
            "status": "completed",
            "stage_label": "Concluido",
            "current_agent_role": "orchestrator",
            "tested_by_team": tested_by_team,
            "approved_by_orchestrator": True,
        }

    if errors:
        return {
            "status": "changes_requested",
            "stage_label": "Ajustes solicitados",
            "current_agent_role": current_role,
            "tested_by_team": tested_by_team,
            "approved_by_orchestrator": False,
        }

    if not subtasks or not task_state.get("senior_directive"):
        return {
            "status": "triage",
            "stage_label": "Em triagem",
            "current_agent_role": "orchestrator",
            "tested_by_team": tested_by_team,
            "approved_by_orchestrator": False,
        }

    if current_role == "planner":
        return {
            "status": "planned",
            "stage_label": "Planejado",
            "current_agent_role": current_role,
            "tested_by_team": tested_by_team,
            "approved_by_orchestrator": False,
        }

    if current_role == "qa":
        return {
            "status": "in_testing",
            "stage_label": "Em testes",
            "current_agent_role": current_role,
            "tested_by_team": tested_by_team,
            "approved_by_orchestrator": False,
        }

    if tested_by_team and task_state.get("quality_approved") and idx >= len(subtasks) - 1:
        return {
            "status": "awaiting_approval",
            "stage_label": "Aguardando aprovacao",
            "current_agent_role": "orchestrator",
            "tested_by_team": tested_by_team,
            "approved_by_orchestrator": False,
        }

    return {
        "status": "in_execution",
        "stage_label": "Em execucao",
        "current_agent_role": current_role,
        "tested_by_team": tested_by_team,
        "approved_by_orchestrator": False,
    }


def _is_task_still_active(task_state: TaskState) -> bool:
    if task_state.get("final_output"):
        return False
    if task_state.get("errors"):
        return False
    return True


def _sync_service_request(task_id: str) -> None:
    request_id = _task_to_service_request.get(task_id)
    if not request_id:
        return

    service_request = _service_requests.get(request_id)
    task_state = _active_tasks.get(task_id)
    if service_request is None:
        return

    progress = _derive_service_request_progress(service_request, task_state)
    last_execution = get_last_execution_entry(task_id)
    service_request.update(progress)
    service_request["last_execution_message"] = last_execution["message"] if last_execution else None
    service_request["last_execution_stage"] = last_execution["stage"] if last_execution else None
    service_request["execution_log_size"] = len(get_execution_log(task_id))
    service_request["updated_at"] = _utc_now_iso()


def _trace_task(
    task_id: str,
    team: str,
    stage: str,
    message: str,
    *,
    level: str = "info",
    agent_id: str | None = None,
    agent_role: str | None = None,
    metadata: dict | None = None,
) -> None:
    entry = append_execution_log(
        task_id=task_id,
        team=team,
        stage=stage,
        message=message,
        level=level,
        agent_id=agent_id,
        agent_role=agent_role,
        metadata=metadata,
    )

    log_line = (
        "[Trace][%s][%s][%s/%s] %s"
        % (
            task_id[:8],
            stage,
            agent_role or "system",
            agent_id or "n/a",
            message,
        )
    )
    if level == "error":
        logger.error(log_line)
    elif level == "warning":
        logger.warning(log_line)
    else:
        logger.info(log_line)

    _sync_service_request(task_id)


def _make_progress_callback(task_id: str):
    """Returns a callback that updates _active_tasks with intermediate state."""
    def _on_progress(intermediate_state):
        if task_id in _active_tasks:
            # Merge only the fields that changed
            for key in ("senior_directive", "subtasks", "current_subtask_index",
                        "agent_outputs", "delivery_evidence", "delivery_manifests",
                        "quality_approved", "final_output", "errors"):
                if key in intermediate_state and intermediate_state[key] is not None:
                    _active_tasks[task_id][key] = intermediate_state[key]
            _sync_service_request(task_id)
    return _on_progress


async def _emit_task_created(task_id: str, team: TeamType, request: str, priority: int) -> None:
    event = OfficialEvent(
        event_type=EventType.TASK_CREATED,
        team=team,
        agent_id="orchestrator_senior_01",
        agent_role=AgentRole.ORCHESTRATOR,
        task_id=task_id,
        payload={"request": request, "priority": priority},
    )
    try:
        await event_bus.emit(event)
    except Exception as exc:
        logger.warning("[API] Falha ao emitir TASK_CREATED para %s: %s", task_id, exc)


async def _run_dev_task(task_id: str, request: str, priority: int):
    """Background task: executa o DevOrchestrator para a tarefa."""
    state = _active_tasks.get(task_id)
    if state is None:
        logger.error(f"[DevTask] Task {task_id} não encontrada no registry.")
        return
    _trace_task(task_id, "dev", "runtime_start", "Execucao da tarefa iniciada no runtime dev.", agent_id="orchestrator_senior_01", agent_role="orchestrator")
    try:
        orchestrator = DevOrchestrator()
        final_state = await orchestrator.run(
            state, on_progress=_make_progress_callback(task_id)
        )
        _active_tasks[task_id] = final_state
        _sync_service_request(task_id)
        _trace_task(task_id, "dev", "runtime_complete", "Execucao da tarefa encerrada com retorno do orquestrador.", agent_id="orchestrator_senior_01", agent_role="orchestrator")
        logger.info(f"[DevTask] Task {task_id} concluída. "
                    f"Output: {len(final_state.get('final_output') or '')} chars.")
    except Exception as exc:
        logger.error(f"[DevTask] Erro na task {task_id}: {exc}", exc_info=True)
        if task_id in _active_tasks:
            _active_tasks[task_id]["errors"].append(str(exc))
            _sync_service_request(task_id)
        _trace_task(task_id, "dev", "runtime_error", f"Falha no runtime dev: {exc}", level="error", agent_id="orchestrator_senior_01", agent_role="orchestrator")


async def _run_marketing_task(task_id: str, request: str, priority: int):
    """Background task: executa o MarketingOrchestrator para a tarefa."""
    state = _active_tasks.get(task_id)
    if state is None:
        logger.error(f"[MarketingTask] Task {task_id} não encontrada no registry.")
        return
    _trace_task(task_id, "marketing", "runtime_start", "Execucao da tarefa iniciada no runtime marketing.", agent_id="orchestrator_senior_01", agent_role="orchestrator")
    try:
        orchestrator = MarketingOrchestrator()
        final_state = await orchestrator.run(
            state, on_progress=_make_progress_callback(task_id)
        )
        _active_tasks[task_id] = final_state
        _sync_service_request(task_id)
        _trace_task(task_id, "marketing", "runtime_complete", "Execucao da tarefa encerrada com retorno do orquestrador.", agent_id="orchestrator_senior_01", agent_role="orchestrator")
        logger.info(f"[MarketingTask] Task {task_id} concluída. "
                    f"Output: {len(final_state.get('final_output') or '')} chars.")
    except Exception as exc:
        logger.error(f"[MarketingTask] Erro na task {task_id}: {exc}", exc_info=True)
        if task_id in _active_tasks:
            _active_tasks[task_id]["errors"].append(str(exc))
            _sync_service_request(task_id)
        _trace_task(task_id, "marketing", "runtime_error", f"Falha no runtime marketing: {exc}", level="error", agent_id="orchestrator_senior_01", agent_role="orchestrator")


async def _enqueue_team_task(
    team: TeamType,
    request: str,
    priority: int,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    task_id = str(uuid.uuid4())
    created_at = _utc_now_iso()
    team_value = team.value

    state = _make_task_state(task_id, team_value, request, priority)
    _active_tasks[task_id] = state
    _trace_task(task_id, team_value, "task_created", "Tarefa enfileirada para execucao.", agent_id="orchestrator_senior_01", agent_role="orchestrator", metadata={"priority": priority})
    await _emit_task_created(task_id, team, request, priority)

    if team == TeamType.DEV:
        background_tasks.add_task(_run_dev_task, task_id, request, priority)
    else:
        background_tasks.add_task(_run_marketing_task, task_id, request, priority)

    logger.info("[API] %s task criada: %s", team_value, task_id)
    return TaskResponse(task_id=task_id, status="queued", team=team_value, created_at=created_at)


# ---------------------------------------------------------------------------
# Routes — Tasks
# ---------------------------------------------------------------------------
@app.post("/tasks/dev", response_model=TaskResponse, status_code=202)
async def create_dev_task(body: TaskRequest, background_tasks: BackgroundTasks):
    """
    Cria uma nova tarefa para o time de Dev.
    Dispara DevOrchestrator em background e retorna imediatamente.
    """
    return await _enqueue_team_task(TeamType.DEV, body.request, body.priority, background_tasks)


@app.post("/tasks/marketing", response_model=TaskResponse, status_code=202)
async def create_marketing_task(body: TaskRequest, background_tasks: BackgroundTasks):
    """
    Cria uma nova tarefa para o time de Marketing.
    Dispara MarketingOrchestrator em background e retorna imediatamente.
    """
    return await _enqueue_team_task(TeamType.MARKETING, body.request, body.priority, background_tasks)


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Retorna o estado atual de uma task pelo seu ID."""
    task = _active_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' não encontrada.")
    return task


@app.get("/tasks/{task_id}/execution-log", response_model=ExecutionLogResponse)
async def get_task_execution_log(task_id: str):
    """Retorna a trilha de execução da tarefa com etapas, agentes e heartbeats."""
    if task_id not in _active_tasks and task_id not in _task_to_service_request:
      raise HTTPException(status_code=404, detail=f"Task '{task_id}' não encontrada.")

    items = [ExecutionLogEntryResponse(**item) for item in get_execution_log(task_id)]
    return ExecutionLogResponse(task_id=task_id, items=items, total=len(items))


@app.get("/tasks/{task_id}/delivery-manifests")
async def get_task_delivery_manifests(task_id: str):
    """Retorna manifestos determinísticos gerados pelo Delivery Runner."""
    task = _active_tasks.get(task_id)
    if task is not None:
        manifests = task.get("delivery_manifests") or {}
        return {"task_id": task_id, "items": manifests, "total": len(manifests)}

    manifest_dir = Path(".runtime") / "delivery-manifests" / task_id
    if not manifest_dir.exists():
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' não encontrada.")

    items: dict[str, dict] = {}
    for file_path in sorted(manifest_dir.glob("*.json")):
        try:
            items[file_path.stem] = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as exc:
            items[file_path.stem] = {"error": str(exc), "manifest_path": str(file_path)}

    return {"task_id": task_id, "items": items, "total": len(items)}


@app.post("/service-requests", response_model=ServiceRequestResponse, status_code=202)
async def create_service_request(body: ServiceRequestCreate, background_tasks: BackgroundTasks):
    """Cria uma solicitação formal para um time e já a liga ao runtime do escritório."""
    team_value = body.team.lower().strip()
    if team_value not in {"dev", "marketing"}:
        raise HTTPException(status_code=400, detail="team deve ser 'dev' ou 'marketing'.")

    team = TeamType.DEV if team_value == "dev" else TeamType.MARKETING
    request_id = str(uuid.uuid4())
    created_at = _utc_now_iso()
    priority = _priority_from_urgency(body.urgency)

    service_request = {
        "request_id": request_id,
        "title": body.title.strip(),
        "team": team_value,
        "status": "received",
        "stage_label": "Recebido",
        "requester_name": body.requester_name,
        "requester_team": body.requester_team,
        "urgency": body.urgency.lower().strip(),
        "priority": priority,
        "desired_due_date": body.desired_due_date,
        "acceptance_criteria": body.acceptance_criteria,
        "request": body.request.strip(),
        "task_id": None,
        "current_agent_role": "orchestrator",
        "tested_by_team": False,
        "approved_by_orchestrator": False,
        "created_at": created_at,
        "updated_at": created_at,
    }

    task_prompt = _build_task_prompt(service_request)
    task_response = await _enqueue_team_task(team, task_prompt, priority, background_tasks)

    service_request["task_id"] = task_response.task_id
    service_request["status"] = "triage"
    service_request["stage_label"] = "Em triagem"
    service_request["updated_at"] = _utc_now_iso()

    _service_requests[request_id] = service_request
    _task_to_service_request[task_response.task_id] = request_id
    _trace_task(
        task_response.task_id,
        team_value,
        "request_intake",
        f"Solicitacao '{service_request['title']}' recebida no portal e vinculada ao backlog.",
        agent_id="orchestrator_senior_01",
        agent_role="orchestrator",
        metadata={"request_id": request_id, "urgency": service_request["urgency"]},
    )
    _sync_service_request(task_response.task_id)

    return ServiceRequestResponse(**_service_requests[request_id])


@app.get("/service-requests", response_model=ServiceRequestListResponse)
async def list_service_requests():
    """Lista o backlog operacional das solicitações com status refletindo o runtime."""
    items = []
    for item in _service_requests.values():
        if item.get("task_id"):
            _sync_service_request(str(item["task_id"]))
        items.append(ServiceRequestResponse(**item))

    items.sort(key=lambda item: item.updated_at, reverse=True)
    return ServiceRequestListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Routes — Agents
# ---------------------------------------------------------------------------
@app.get("/agents", response_model=list[AgentStatus])
async def list_agents():
    """
    Retorna a lista de todos os agentes registrados e seus estados atuais.
    O registro é populado pelos próprios agentes ao serem instanciados/atualizados.
    """
    seed_agent_registry()
    return [
        AgentStatus(
            agent_id=agent["agent_id"],
            role=agent["agent_role"],
            team=agent["team"],
            status=agent["status"],
            current_task_id=agent.get("current_task_id"),
            completed_tasks=agent.get("completed_tasks", 0),
            error_count=agent.get("error_count", 0),
            position=agent.get("position", {"x": 0, "y": 0}),
        )
        for agent in sorted(agent_registry.values(), key=lambda item: (item["team"], item["agent_role"]))
    ]


@app.get("/agents/{agent_id}/config", response_model=AgentPersonalityConfig)
async def get_agent_personality_config(agent_id: str):
    """Retorna a configuracao editavel de personalidade e operacao do agente."""
    seed_agent_registry()
    agent = agent_registry.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' nao encontrado.")
    return AgentPersonalityConfig(**get_agent_config(agent))


@app.patch("/agents/{agent_id}/config", response_model=AgentPersonalityConfig)
async def patch_agent_personality_config(agent_id: str, body: AgentPersonalityUpdate):
    """Atualiza a configuracao operacional usada em futuras execucoes do agente."""
    seed_agent_registry()
    agent = agent_registry.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' nao encontrado.")

    payload = body.model_dump(exclude_unset=True)
    config = update_agent_config(agent, payload)
    return AgentPersonalityConfig(**config)


@app.get("/agents/{agent_id}/capabilities", response_model=AgentCapabilities)
async def get_agent_capabilities(agent_id: str):
    """Retorna as ferramentas e MCPs liberados para o papel do agente."""
    seed_agent_registry()
    agent = agent_registry.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' nao encontrado.")

    role = str(agent["agent_role"])
    return AgentCapabilities(
        agent_id=agent_id,
        role=role,
        team=str(agent["team"]),
        tool_policy=get_role_tool_policy(role),
        picoclaw=get_picoclaw_status(),
    )


# ---------------------------------------------------------------------------
# Routes — Health
# ---------------------------------------------------------------------------
@app.get("/health", response_model=SystemHealth)
async def health_check():
    """
    Verifica status do sistema: API, Redis e Ollama com modelos disponíveis.
    """
    # Redis
    redis_status = "offline"
    event_bus_status = event_bus.mode
    event_bus_persistent = event_bus.is_persistent
    try:
        if event_bus.is_available:
            await event_bus._redis.ping()
            redis_status = "online" if event_bus.is_persistent else "degraded_fake"
    except Exception as exc:
        logger.warning(f"[Health] Redis ping falhou: {exc}")
        event_bus_status = "offline"
        event_bus_persistent = False

    # Ollama
    ollama_info = await check_ollama_health()
    ollama_status = ollama_info.get("status", "offline")
    # models pode ser list[dict] ({"name":..,"size_gb":..}) ou list[str]
    raw_models = ollama_info.get("models", [])
    available_models: list[str] = [
        m["name"] if isinstance(m, dict) else str(m) for m in raw_models
    ]

    active_tasks_count = sum(
        1 for task_state in _active_tasks.values() if _is_task_still_active(task_state)
    )

    return SystemHealth(
        api="online",
        redis=redis_status,
        event_bus=event_bus_status,
        event_bus_persistent=event_bus_persistent,
        ollama=ollama_status,
        available_models=available_models,
        brain_router=get_brain_status(),
        model_gate=gate.get_usage_summary(),
        picoclaw=await check_picoclaw_health(),
        active_tasks=active_tasks_count,
    )


@app.get("/models/brain-router")
async def get_brain_router_status():
    """Retorna perfis de cerebro por agente e selecoes recentes de modelo."""
    return get_brain_status()


@app.get("/models/approved")
async def list_approved_models():
    """Lista modelos liberados pelo gate de custo e seguranca."""
    return {"items": gate.list_approved(), "usage": gate.get_usage_summary()}


@app.get("/integrations/picoclaw")
async def get_picoclaw_integration_status():
    """Retorna status e politica operacional do PicoClaw MCP bridge."""
    return {
        "runtime": await check_picoclaw_health(),
        "config": get_picoclaw_status(),
        "policy": list_tool_policies(),
    }


@app.get("/tool-governance")
async def get_tool_governance():
    """Retorna a matriz de permissao para MCPs e ferramentas de agentes."""
    return list_tool_policies()


# ---------------------------------------------------------------------------
# Routes — Event History
# ---------------------------------------------------------------------------
@app.get("/events/history", response_model=EventHistoryResponse)
async def get_event_history():
    """
    Retorna os últimos 500 eventos do EventBus para replay no frontend.
    """
    try:
        events = await event_bus.get_history(count=500)
    except Exception as exc:
        logger.error(f"[API] Falha ao buscar histórico de eventos: {exc}")
        raise HTTPException(status_code=503, detail="EventBus indisponível.")

    return EventHistoryResponse(events=events, total=len(events))


# ---------------------------------------------------------------------------
# Routes — Improvement Loop
# ---------------------------------------------------------------------------

@app.get("/improvements/pending")
async def list_pending_improvements():
    """
    Retorna propostas de melhoria pendentes de aprovação.
    Geradas automaticamente após cada tarefa completada.
    """
    proposals = improvement_loop.get_pending_proposals()
    return {"proposals": [p.to_dict() for p in proposals], "total": len(proposals)}


@app.post("/improvements/{proposal_id}/approve")
async def approve_improvement(proposal_id: str, comment: str = ""):
    """Aprova uma proposta de melhoria e cria a tarefa correspondente."""
    await improvement_loop.process_approval(proposal_id, approved=True, user_comment=comment)
    return {"status": "approved", "proposal_id": proposal_id}


@app.post("/improvements/{proposal_id}/reject")
async def reject_improvement(proposal_id: str, comment: str = ""):
    """Rejeita uma proposta de melhoria com comentário opcional."""
    await improvement_loop.process_approval(proposal_id, approved=False, user_comment=comment)
    return {"status": "rejected", "proposal_id": proposal_id}


@app.get("/improvements/metrics")
async def improvement_metrics():
    """Métricas agregadas do ciclo de melhoria: totais por status, categoria e impacto."""
    return await improvement_loop.get_improvement_metrics()


# ---------------------------------------------------------------------------
# Routes — Cross-Team Handoff
# ---------------------------------------------------------------------------

@app.post("/tasks/handoff")
async def request_handoff(
    from_team: str,
    to_team: str,
    from_agent_id: str,
    context: str,
    deliverable_needed: str,
    priority: int = 1,
    original_task_id: str | None = None,
):
    """
    Cria um handoff entre times (ex.: Dev → Marketing).
    O time receptor recebe notificação via EventBus e o canvas anima o agente se movendo.
    """
    handoff = await create_handoff(
        from_team=from_team,
        to_team=to_team,
        from_agent_id=from_agent_id,
        context=context,
        deliverable_needed=deliverable_needed,
        priority=priority,
        original_task_id=original_task_id,
    )
    return handoff.to_dict()


@app.get("/tasks/handoffs/{team}")
async def list_handoffs(team: str):
    """Lista handoffs pendentes para um time (ex.: /tasks/handoffs/marketing)."""
    pending = get_pending_handoffs(team)
    return {"handoffs": [h.to_dict() for h in pending], "total": len(pending)}


@app.post("/tasks/handoffs/{handoff_id}/resolve")
async def mark_handoff_resolved(handoff_id: str):
    """Marca um handoff como resolvido após o time receptor iniciar a tarefa."""
    ok = resolve_handoff(handoff_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Handoff '{handoff_id}' não encontrado.")
    return {"status": "resolved", "handoff_id": handoff_id}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    """
    WebSocket bridge — /ws
    Conecta o frontend ao EventBus em tempo real com replay de histórico.
    """
    await websocket_endpoint(websocket)
