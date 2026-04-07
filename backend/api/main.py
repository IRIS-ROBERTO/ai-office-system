"""
AI Office System — FastAPI Main Application
Entrada HTTP/WebSocket do sistema. Gerencia tarefas, agentes e saúde.
"""
import asyncio
import logging
import json
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.core.event_bus import event_bus
from backend.core.state import TaskState, AgentState
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
_agent_registry: dict[str, AgentState] = {}


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Conecta EventBus + Redis no startup; desconecta no shutdown."""
    logger.info("[Lifespan] Iniciando AI Office System...")
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


async def _run_dev_task(task_id: str, request: str, priority: int):
    """Background task: executa o DevOrchestrator para a tarefa."""
    state = _active_tasks.get(task_id)
    if state is None:
        logger.error(f"[DevTask] Task {task_id} não encontrada no registry.")
        return
    try:
        orchestrator = DevOrchestrator()
        result = await orchestrator.run(state)
        if result:
            _active_tasks[task_id] = result
        logger.info(f"[DevTask] Task {task_id} concluída.")
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
        result = await orchestrator.run(state)
        if result:
            _active_tasks[task_id] = result
        logger.info(f"[MarketingTask] Task {task_id} concluída.")
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
    return [
        AgentStatus(
            agent_id=agent["agent_id"],
            role=agent["agent_role"],
            team=agent["team"],
            status=agent["status"],
            current_task_id=agent.get("current_task_id"),
            completed_tasks=agent.get("completed_tasks", 0),
        )
        for agent in _agent_registry.values()
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
    available_models: list[str] = ollama_info.get("models", [])

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
