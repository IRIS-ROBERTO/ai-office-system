"""
AI Office System — FastAPI Main Application
Entrada HTTP/WebSocket do sistema. Gerencia tarefas, agentes e saúde.
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import httpx

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.core.event_bus import event_bus
from backend.core.gold_standard import GENERATED_PROJECTS_ROOT
from backend.core.delivery_audit import get_task_delivery_audit, list_delivery_audits
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
from backend.core.agent_capability_matrix import build_agent_capability, build_agent_capability_matrix
from backend.core.agent_runtime_gateway import get_runtime_gateway_status
from backend.core.memory_gateway import memory_gateway
from backend.core.production_readiness import build_production_readiness_report
from backend.core.tool_governance import get_role_tool_policy, list_tool_policies
from backend.core.application_factory import create_application_from_insight
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
    MemoryCreateRequest,
    DeliveryAuditListResponse,
    DeliveryAuditTaskResponse,
    ProductionReadinessResponse,
    ResearchFindingsResponse,
    ResearchStatsResponse,
    ResearchScheduleConfig,
    ResearchScheduleUpdate,
    ResearchScrapeResponse,
)
from backend.api.websocket import websocket_endpoint
from backend.core import research_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estado in-memory: tasks e agentes rastreados em runtime
# ---------------------------------------------------------------------------
_active_tasks: dict[str, TaskState] = {}
_tasks_lock = threading.Lock()                  # protege _active_tasks de race conditions
_service_requests: dict[str, dict] = {}
_task_to_service_request: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Rate limiting simples por IP (sem dependência externa)
# ---------------------------------------------------------------------------
_rate_counters: dict[str, list[float]] = defaultdict(list)  # ip → [timestamps]
_RATE_LIMIT_MAX = 10         # máximo de requests por IP
_RATE_LIMIT_WINDOW = 60.0    # janela em segundos


def _check_rate_limit(client_ip: str) -> bool:
    """Retorna True se o IP está dentro do limite. Thread-safe via GIL em list ops."""
    import time
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW
    timestamps = _rate_counters[client_ip]
    # Remove timestamps fora da janela
    _rate_counters[client_ip] = [t for t in timestamps if t > window_start]
    if len(_rate_counters[client_ip]) >= _RATE_LIMIT_MAX:
        return False
    _rate_counters[client_ip].append(now)
    return True


# ---------------------------------------------------------------------------
# Limpeza automática de tasks finalizadas (evita memory leak)
# ---------------------------------------------------------------------------
_TASKS_MAX_COMPLETED = 200   # mantém no máximo N tasks concluídas em memória


def _cleanup_completed_tasks() -> int:
    """Remove tasks finalizadas além do limite. Retorna quantidade removida."""
    with _tasks_lock:
        completed = [
            tid for tid, state in _active_tasks.items()
            if not _is_task_still_active(state)
        ]
        to_remove = completed[:-_TASKS_MAX_COMPLETED] if len(completed) > _TASKS_MAX_COMPLETED else []
        for tid in to_remove:
            _active_tasks.pop(tid, None)
    return len(to_remove)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------
async def _restore_tasks_from_supabase() -> None:
    """
    Recupera tasks persistidas no Supabase e restaura _active_tasks em memória.
    Tasks que estavam 'running' são marcadas como interrompidas (processo reiniciou).
    Falhas silenciosas — nunca bloqueia o boot.
    """
    from backend.core.supabase_repository import SupabaseRepository
    from backend.config.settings import settings
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        logger.info("[Lifespan] Supabase não configurado — restauração de tasks ignorada.")
        return
    try:
        repo = SupabaseRepository()
        rows = await repo.list_tasks(limit=100)
        restored = 0
        for row in rows:
            task_id = row.get("task_id") or row.get("id")
            if not task_id or task_id in _active_tasks:
                continue
            status = row.get("status", "")
            errors: list[str] = []
            if status == "running":
                errors = ["Task interrompida pelo restart do servidor. Re-submeta se necessário."]
            state: TaskState = TaskState(
                task_id=task_id,
                team=row.get("team", ""),
                original_request=row.get("request", ""),
                senior_directive=row.get("senior_directive"),
                subtasks=row.get("subtasks") or [],
                current_subtask_index=0,
                agent_outputs=row.get("agent_outputs") or {},
                delivery_evidence={},
                delivery_manifests={},
                quality_approved=False,
                retry_count=row.get("retry_count", 0),
                final_output=row.get("final_output"),
                errors=errors,
                messages=[],
            )
            with _tasks_lock:
                _active_tasks[task_id] = state
            restored += 1
        if restored:
            logger.info("[Lifespan] %d tasks restauradas do Supabase.", restored)
    except Exception as exc:
        logger.warning("[Lifespan] Restauração do Supabase falhou (não crítico): %s", exc)


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

    # Inicializa Research Store e scheduler
    research_store.initialize()
    research_store.start_scheduler()
    logger.info("[Lifespan] Research Store e Scheduler iniciados.")

    # Restaura tasks persistidas do Supabase (best-effort, nunca bloqueia boot)
    await _restore_tasks_from_supabase()

    yield

    logger.info("[Lifespan] Encerrando AI Office System...")
    research_store.stop_scheduler()
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


def _save_task_report(task_id: str, team: str, output: str) -> str | None:
    """Persiste o output final em disco em GENERATED_PROJECTS_ROOT/<task_id>/.
    Retorna o caminho absoluto do relatório, ou None se falhar.
    """
    if not output.strip():
        return None
    try:
        report_dir = GENERATED_PROJECTS_ROOT / task_id
        report_dir.mkdir(parents=True, exist_ok=True)

        report_path = report_dir / "relatorio.md"
        report_path.write_text(output, encoding="utf-8")

        readme_path = report_dir / "README.md"
        readme_path.write_text(
            f"# Relatório Intel Scout — {task_id}\n\n"
            f"**Gerado por:** IRIS AI Office System — Time {team.upper()}  \n"
            f"**Data:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            "## Como usar este relatório\n\n"
            "1. Leia `relatorio.md` para a análise completa dos agentes IRIS\n"
            "2. Use a seção **Top Projetos** para priorizar integrações\n"
            "3. Apresente o conteúdo de **Potencial Comercial** para stakeholders\n"
            "4. Para implementação técnica, encaminhe ao Time DEV via Command Center\n\n"
            "## Estrutura dos arquivos\n\n"
            "| Arquivo | Conteúdo |\n"
            "|---------|----------|\n"
            "| `relatorio.md` | Análise completa + subtarefas executadas pelos agentes |\n"
            "| `README.md` | Este arquivo — instruções de uso |\n\n"
            "## Como executar / reproduzir\n\n"
            "Este relatório foi gerado automaticamente pelo agente SCOUT-01 do IRIS.\n"
            "Para gerar um novo relatório atualizado:\n\n"
            "```bash\n"
            "# 1. Abrir IRIS\n"
            "IRIS.bat\n\n"
            "# 2. Navegar para: Intel Hub → aba Intel Scout\n"
            "# 3. Clicar em 'Raspar Agora' para atualizar os findings\n"
            "# 4. Clicar em '⚡ Insights' → selecionar categoria → 'Executar com Agentes IRIS'\n"
            "```\n",
            encoding="utf-8",
        )

        logger.info("[Report] Relatório salvo em: %s", report_path)
        return str(report_path)
    except Exception as exc:
        logger.warning("[Report] Falha ao salvar relatório para %s: %s", task_id, exc)
        return None


async def _github_upload_file(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    path: str,
    content_bytes: bytes,
    message: str,
) -> bool:
    """Faz upload de um arquivo via GitHub Contents API. Atualiza se já existir."""
    import base64
    encoded = base64.b64encode(content_bytes).decode()
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    # Verifica SHA existente para update
    check = await client.get(url)
    payload: dict = {"message": message, "content": encoded}
    if check.status_code == 200:
        payload["sha"] = check.json().get("sha", "")
    resp = await client.put(url, json=payload)
    if resp.status_code not in (200, 201):
        logger.warning("[GitHub] upload %s → %s: %s", path, resp.status_code, resp.text[:200])
        return False
    return True


async def _push_project_to_github(task_id: str, project_dir: Path) -> str | None:
    """
    Publica os artefatos do relatório Intel Scout no repositório ai-office-system
    via GitHub Contents API (não requer criação de novo repo).

    Diretório no repo: intel-scout-reports/<task_id>/
    Retorna a URL da pasta no GitHub ou None em caso de falha.
    """
    if not settings.GITHUB_TOKEN:
        return None
    if not project_dir.exists():
        return None

    owner = settings.GITHUB_DEFAULT_ORG or settings.GITHUB_USERNAME
    repo = "ai-office-system"
    base_path = f"intel-scout-reports/{task_id}"
    commit_msg = f"feat(intel-scout): relatório de análise {task_id[:8]}"

    headers = {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            uploaded = 0
            for filename in ("relatorio.md", "README.md"):
                file_path = project_dir / filename
                if not file_path.exists():
                    continue
                ok = await _github_upload_file(
                    client, owner, repo,
                    f"{base_path}/{filename}",
                    file_path.read_bytes(),
                    commit_msg,
                )
                if ok:
                    uploaded += 1

            if uploaded == 0:
                logger.warning("[GitHub] Nenhum arquivo publicado para %s.", task_id)
                return None

            github_url = f"https://github.com/{owner}/{repo}/tree/main/{base_path}"
            logger.info("[GitHub] %d arquivo(s) publicados: %s", uploaded, github_url)
            return github_url
    except Exception as exc:
        logger.warning("[GitHub] _push_project_to_github falhou para %s: %s", task_id, exc)
    return None


async def _push_iris_repo_to_github() -> bool:
    """
    Faz push do repositório IRIS local (ai-office-system) para o GitHub.
    Chamada após tarefas DEV que modificam o próprio código da plataforma.
    Retorna True se o push teve sucesso.
    """
    if not settings.GITHUB_TOKEN:
        return False
    try:
        from backend.core.gold_standard import REPO_ROOT
        safe_token = quote(settings.GITHUB_TOKEN, safe="")
        owner = settings.GITHUB_DEFAULT_ORG or settings.GITHUB_USERNAME
        push_url = f"https://x-access-token:{safe_token}@github.com/{owner}/ai-office-system.git"

        result = subprocess.run(
            ["git", "push", push_url, "HEAD:main"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("[GitHub] Push do IRIS realizado.")
            return True
        logger.warning("[GitHub] Push IRIS falhou: %s", (result.stderr or "")[:300])
    except Exception as exc:
        logger.warning("[GitHub] _push_iris_repo_to_github falhou: %s", exc)
    return False


def _make_progress_callback(task_id: str):
    """Returns a callback that updates _active_tasks with intermediate state (thread-safe)."""
    def _on_progress(intermediate_state):
        with _tasks_lock:
            if task_id not in _active_tasks:
                return
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
        report_path = _save_task_report(task_id, "dev", final_state.get("final_output") or "")
        if report_path:
            final_state["report_path"] = report_path
            github_url = await _push_project_to_github(task_id, GENERATED_PROJECTS_ROOT / task_id)
            if github_url:
                final_state["github_url"] = github_url
        # Push IRIS local repo se houve commits aprovados (tarefas de melhoria da plataforma)
        manifests = final_state.get("delivery_manifests") or {}
        if any(m.get("approved") for m in manifests.values()):
            await _push_iris_repo_to_github()
        with _tasks_lock:
            _active_tasks[task_id] = final_state
        _sync_service_request(task_id)
        _trace_task(task_id, "dev", "runtime_complete", "Execucao da tarefa encerrada com retorno do orquestrador.", agent_id="orchestrator_senior_01", agent_role="orchestrator")
        logger.info(f"[DevTask] Task {task_id} concluída. "
                    f"Output: {len(final_state.get('final_output') or '')} chars.")
    except Exception as exc:
        logger.error(f"[DevTask] Erro na task {task_id}: {exc}", exc_info=True)
        with _tasks_lock:
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
        report_path = _save_task_report(task_id, "marketing", final_state.get("final_output") or "")
        if report_path:
            final_state["report_path"] = report_path
            github_url = await _push_project_to_github(task_id, GENERATED_PROJECTS_ROOT / task_id)
            if github_url:
                final_state["github_url"] = github_url
        with _tasks_lock:
            _active_tasks[task_id] = final_state
        _sync_service_request(task_id)
        _trace_task(task_id, "marketing", "runtime_complete", "Execucao da tarefa encerrada com retorno do orquestrador.", agent_id="orchestrator_senior_01", agent_role="orchestrator")
        logger.info(f"[MarketingTask] Task {task_id} concluída. "
                    f"Output: {len(final_state.get('final_output') or '')} chars.")
    except Exception as exc:
        logger.error(f"[MarketingTask] Erro na task {task_id}: {exc}", exc_info=True)
        with _tasks_lock:
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
    with _tasks_lock:
        _active_tasks[task_id] = state
    _cleanup_completed_tasks()
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
async def create_dev_task(request: Request, body: TaskRequest, background_tasks: BackgroundTasks):
    """
    Cria uma nova tarefa para o time de Dev.
    Dispara DevOrchestrator em background e retorna imediatamente.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Muitas requisições. Tente novamente em 1 minuto.")
    return await _enqueue_team_task(TeamType.DEV, body.request, body.priority, background_tasks)


@app.post("/tasks/marketing", response_model=TaskResponse, status_code=202)
async def create_marketing_task(request: Request, body: TaskRequest, background_tasks: BackgroundTasks):
    """
    Cria uma nova tarefa para o time de Marketing.
    Dispara MarketingOrchestrator em background e retorna imediatamente.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Muitas requisições. Tente novamente em 1 minuto.")
    return await _enqueue_team_task(TeamType.MARKETING, body.request, body.priority, background_tasks)


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Retorna o estado atual de uma task pelo seu ID."""
    task = _active_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' não encontrada.")
    return task


@app.get("/tasks/{task_id}/report")
async def get_task_report(task_id: str):
    """Retorna o relatório gerado em disco pelo orchestrator para a task."""
    task = _active_tasks.get(task_id)
    report_path_str = task.get("report_path") if task else None
    github_url = task.get("github_url") if task else None

    if not report_path_str:
        candidate = GENERATED_PROJECTS_ROOT / task_id / "relatorio.md"
        if candidate.exists():
            report_path_str = str(candidate)

    if not report_path_str:
        return {"exists": False, "path": None, "content": None, "task_id": task_id, "github_url": github_url}

    report_path = Path(report_path_str)
    if not report_path.exists():
        return {"exists": False, "path": report_path_str, "content": None, "task_id": task_id, "github_url": github_url}

    content = report_path.read_text(encoding="utf-8", errors="replace")
    return {
        "exists": True,
        "path": report_path_str,
        "content": content,
        "task_id": task_id,
        "size_chars": len(content),
        "github_url": github_url,
    }


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


@app.get("/delivery-audit", response_model=DeliveryAuditListResponse)
async def list_delivery_audit_endpoint(
    limit: int = 50,
    approved: bool | None = None,
):
    """Lista auditoria executiva das entregas verificadas por manifestos."""
    return list_delivery_audits(limit=limit, approved=approved)


@app.get("/delivery-audit/{task_id}", response_model=DeliveryAuditTaskResponse)
async def get_delivery_audit_endpoint(task_id: str):
    """Retorna auditoria completa de entrega para uma tarefa específica."""
    try:
        return get_task_delivery_audit(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' não encontrada.")


@app.post("/service-requests", response_model=ServiceRequestResponse, status_code=202)
async def create_service_request(request: Request, body: ServiceRequestCreate, background_tasks: BackgroundTasks):
    """Cria uma solicitação formal para um time e já a liga ao runtime do escritório."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Muitas requisições. Tente novamente em 1 minuto.")
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
    try:
        return AgentCapabilities(**build_agent_capability(agent_id))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' nao encontrado.")


@app.get("/agents/capabilities/matrix")
async def get_agent_capabilities_matrix():
    """Retorna matriz auditavel de autonomia, segmentacao, tools, memoria e MCPs."""
    return build_agent_capability_matrix()


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
        runtime_gateway=await get_runtime_gateway_status(),
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


@app.get("/integrations/runtime-gateway")
async def get_agent_runtime_gateway():
    """Retorna provedores de runtime avaliados e a decisão operacional ativa."""
    return await get_runtime_gateway_status()


@app.get("/integrations/memory-gateway")
async def get_memory_gateway_status():
    """Retorna status da memoria governada local e classes liberadas."""
    return memory_gateway.status()


@app.get("/memory/search")
async def search_memory(
    query: str,
    memory_class: str | None = None,
    agent_role: str | None = None,
    limit: int = 10,
):
    """Busca memorias aprovadas por texto simples, classe e papel do agente."""
    return {
        "query": query,
        "items": memory_gateway.search(
            query=query,
            memory_class=memory_class,
            agent_role=agent_role,
            limit=limit,
        ),
        "external_items": memory_gateway.search_external(query=query, limit=limit),
    }


@app.get("/memory")
async def list_memory(
    memory_class: str | None = None,
    agent_role: str | None = None,
    limit: int = 50,
):
    """Lista memorias governadas mais recentes."""
    return {
        "items": [
            record.to_dict()
            for record in memory_gateway.list_memories(
                memory_class=memory_class,
                agent_role=agent_role,
                limit=limit,
            )
        ]
    }


@app.post("/memory")
async def create_memory(body: MemoryCreateRequest):
    """Cria memoria manual aprovada pelo operador, com bloqueio de segredos."""
    result = memory_gateway.remember(**body.model_dump())
    if not result.stored:
        raise HTTPException(status_code=400, detail=result.to_dict())
    return result.to_dict()


@app.get("/production-readiness", response_model=ProductionReadinessResponse)
async def get_production_readiness():
    """Executa o release gate objetivo para indicar readiness de producao."""
    health = await health_check()
    health_payload = health.model_dump() if hasattr(health, "model_dump") else dict(health)
    audit_payload = list_delivery_audits(limit=250)
    return build_production_readiness_report(
        health=health_payload,
        delivery_audit=audit_payload,
    )


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
# Research / Intel — SCOUT endpoints
# ---------------------------------------------------------------------------

@app.get("/research/findings", response_model=ResearchFindingsResponse)
async def get_research_findings(
    source: str | None = None,
    min_score: int = 0,
    grade: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    Retorna os findings do agente SCOUT.
    Filtrável por source (github, huggingface, huggingface_space, combination),
    min_score e grade (S/A/B/C/D).
    """
    result = research_store.get_findings(
        source=source,
        min_score=min_score,
        grade=grade,
        limit=limit,
        offset=offset,
    )
    return result


@app.get("/research/stats", response_model=ResearchStatsResponse)
async def get_research_stats():
    """Estatísticas agregadas dos findings (por fonte, grade, score médio)."""
    return research_store.get_stats()


@app.get("/research/schedule", response_model=ResearchScheduleConfig)
async def get_research_schedule():
    """Retorna a configuração atual de agendamento do SCOUT."""
    return research_store.get_config()


@app.patch("/research/schedule", response_model=ResearchScheduleConfig)
async def update_research_schedule(body: ResearchScheduleUpdate):
    """Atualiza a configuração de agendamento do SCOUT."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
    config = research_store.update_config(updates)
    return config


@app.post("/research/scrape", response_model=ResearchScrapeResponse)
async def trigger_research_scrape(background_tasks: BackgroundTasks):
    """
    Dispara uma raspagem imediata do SCOUT (GitHub + GitLab + HuggingFace).
    Executa em background para não bloquear a resposta.
    """
    status = research_store.get_scheduler_status()
    if status.get("running"):
        return ResearchScrapeResponse(
            status="already_running",
            message="Raspagem já em andamento. Aguarde a conclusão.",
        )

    async def _emit_research_event(event_type: str, payload: dict) -> None:
        from backend.core.event_types import AgentRole, TeamType
        event = OfficialEvent(
            event_type=EventType.RESEARCH_STARTED if event_type == "research_started" else EventType.RESEARCH_COMPLETED,
            team=TeamType.INTEL,
            agent_id="intel_scout_01",
            agent_role=AgentRole.SCOUT,
            payload=payload,
        )
        try:
            await event_bus.emit(event)
        except Exception as exc:
            logger.warning(f"[Research] Falha ao emitir evento {event_type}: {exc}")

    background_tasks.add_task(research_store.run_scrape, _emit_research_event)
    return ResearchScrapeResponse(
        status="started",
        message="Raspagem iniciada em background. Resultados disponíveis em /research/findings.",
        started_at=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/research/scheduler/status")
async def get_research_scheduler_status():
    """Status do scheduler de pesquisa (ativo, último run, próximo run)."""
    return research_store.get_scheduler_status()


@app.get("/research/insights")
async def get_research_insights():
    """Gera insights de melhoria baseados nos findings do SCOUT."""
    return research_store.generate_insights()


@app.post("/research/insights/{category_id}/promote")
async def promote_research_insight(category_id: str):
    """Promove uma categoria de insight para plano versionado e commitado."""
    try:
        result = research_store.promote_insight(category_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Insight '{category_id}' não encontrado.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao promover insight: {exc}")

    pushed = await _push_iris_repo_to_github()
    result["pushed_to_github"] = pushed
    return result


@app.post("/research/insights/{category_id}/create-application")
async def create_research_application(category_id: str):
    """Cria uma aplicação inicial a partir de insight, respeitando a estratégia de repositório."""
    insights = research_store.generate_insights().get("insights", [])
    insight = next((item for item in insights if item.get("category_id") == category_id), None)
    if not insight:
        raise HTTPException(status_code=404, detail=f"Insight '{category_id}' não encontrado.")

    try:
        result = create_application_from_insight(insight)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao criar aplicação: {exc}")

    if result.get("repo_strategy") == "iris_repository":
        result["pushed_to_github"] = await _push_iris_repo_to_github()
    return result


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
