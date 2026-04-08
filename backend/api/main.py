"""
AI Office System — FastAPI Main Application
Entrada HTTP/WebSocket do sistema. Gerencia tarefas, agentes e saúde.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.core.event_bus import event_bus
from backend.core.state import TaskState
from backend.core.event_types import AgentRole, EventType, OfficialEvent, TeamType
from backend.core.runtime_registry import agent_registry, seed_agent_registry
from backend.config.settings import settings
from backend.tools.ollama_tool import check_ollama_health
from backend.orchestrator import DevOrchestrator, MarketingOrchestrator
from backend.api.schemas import (
    TaskRequest,
    TaskResponse,
    AgentStatus,
    SystemHealth,
    EventHistoryResponse,
)
from backend.api.websocket import websocket_endpoint

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estado in-memory: tasks e agentes rastreados em runtime
# ---------------------------------------------------------------------------
_active_tasks: dict[str, TaskState] = {}


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
        quality_approved=False,
        retry_count=0,
        final_output=None,
        errors=[],
        messages=[],
    )


def _make_progress_callback(task_id: str):
    """Returns a callback that updates _active_tasks with intermediate state."""
    def _on_progress(intermediate_state):
        if task_id in _active_tasks:
            # Merge only the fields that changed
            for key in ("senior_directive", "subtasks", "current_subtask_index",
                        "agent_outputs", "quality_approved", "final_output", "errors"):
                if key in intermediate_state and intermediate_state[key] is not None:
                    _active_tasks[task_id][key] = intermediate_state[key]
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
    try:
        orchestrator = DevOrchestrator()
        final_state = await orchestrator.run(
            state, on_progress=_make_progress_callback(task_id)
        )
        _active_tasks[task_id] = final_state
        logger.info(f"[DevTask] Task {task_id} concluída. "
                    f"Output: {len(final_state.get('final_output') or '')} chars.")
    except Exception as exc:
        logger.error(f"[DevTask] Erro na task {task_id}: {exc}", exc_info=True)
        if task_id in _active_tasks:
            _active_tasks[task_id]["errors"].append(str(exc))


async def _run_marketing_task(task_id: str, request: str, priority: int):
    """Background task: executa o MarketingOrchestrator para a tarefa."""
    state = _active_tasks.get(task_id)
    if state is None:
        logger.error(f"[MarketingTask] Task {task_id} não encontrada no registry.")
        return
    try:
        orchestrator = MarketingOrchestrator()
        final_state = await orchestrator.run(
            state, on_progress=_make_progress_callback(task_id)
        )
        _active_tasks[task_id] = final_state
        logger.info(f"[MarketingTask] Task {task_id} concluída. "
                    f"Output: {len(final_state.get('final_output') or '')} chars.")
    except Exception as exc:
        logger.error(f"[MarketingTask] Erro na task {task_id}: {exc}", exc_info=True)
        if task_id in _active_tasks:
            _active_tasks[task_id]["errors"].append(str(exc))


# ---------------------------------------------------------------------------
# Routes — Tasks
# ---------------------------------------------------------------------------
@app.post("/tasks/dev", response_model=TaskResponse, status_code=202)
async def create_dev_task(body: TaskRequest, background_tasks: BackgroundTasks):
    """
    Cria uma nova tarefa para o time de Dev.
    Dispara DevOrchestrator em background e retorna imediatamente.
    """
    task_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    state = _make_task_state(task_id, "dev", body.request, body.priority)
    _active_tasks[task_id] = state
    await _emit_task_created(task_id, TeamType.DEV, body.request, body.priority)

    background_tasks.add_task(_run_dev_task, task_id, body.request, body.priority)
    logger.info(f"[API] Dev task criada: {task_id}")

    return TaskResponse(
        task_id=task_id,
        status="queued",
        team="dev",
        created_at=created_at,
    )


@app.post("/tasks/marketing", response_model=TaskResponse, status_code=202)
async def create_marketing_task(body: TaskRequest, background_tasks: BackgroundTasks):
    """
    Cria uma nova tarefa para o time de Marketing.
    Dispara MarketingOrchestrator em background e retorna imediatamente.
    """
    task_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    state = _make_task_state(task_id, "marketing", body.request, body.priority)
    _active_tasks[task_id] = state
    await _emit_task_created(task_id, TeamType.MARKETING, body.request, body.priority)

    background_tasks.add_task(_run_marketing_task, task_id, body.request, body.priority)
    logger.info(f"[API] Marketing task criada: {task_id}")

    return TaskResponse(
        task_id=task_id,
        status="queued",
        team="marketing",
        created_at=created_at,
    )


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Retorna o estado atual de uma task pelo seu ID."""
    task = _active_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' não encontrada.")
    return task


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
    try:
        if event_bus._redis is not None:
            await event_bus._redis.ping()
            redis_status = "online"
    except Exception as exc:
        logger.warning(f"[Health] Redis ping falhou: {exc}")

    # Ollama
    ollama_info = await check_ollama_health()
    ollama_status = ollama_info.get("status", "offline")
    # models pode ser list[dict] ({"name":..,"size_gb":..}) ou list[str]
    raw_models = ollama_info.get("models", [])
    available_models: list[str] = [
        m["name"] if isinstance(m, dict) else str(m) for m in raw_models
    ]

    active_tasks_count = len(_active_tasks)

    return SystemHealth(
        api="online",
        redis=redis_status,
        ollama=ollama_status,
        available_models=available_models,
        active_tasks=active_tasks_count,
    )


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
# WebSocket
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    """
    WebSocket bridge — /ws
    Conecta o frontend ao EventBus em tempo real com replay de histórico.
    """
    await websocket_endpoint(websocket)
