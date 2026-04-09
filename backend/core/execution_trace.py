"""
AI Office System — Execution Trace
Registro estruturado e em memória do progresso de cada tarefa.

Objetivo:
  - Permitir inspeção de qual etapa está rodando agora
  - Expor heartbeat quando uma subtarefa demora demais
  - Mostrar o último agente/etapa visível para backlog e debugging
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import TypedDict


class ExecutionLogEntry(TypedDict):
    timestamp: str
    stage: str
    message: str
    level: str
    team: str
    task_id: str
    agent_id: str | None
    agent_role: str | None
    metadata: dict


_execution_logs: dict[str, list[ExecutionLogEntry]] = defaultdict(list)
_lock = Lock()
_MAX_ENTRIES_PER_TASK = 200


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_execution_log(
    task_id: str,
    team: str,
    stage: str,
    message: str,
    *,
    level: str = "info",
    agent_id: str | None = None,
    agent_role: str | None = None,
    metadata: dict | None = None,
) -> ExecutionLogEntry:
    entry: ExecutionLogEntry = {
        "timestamp": _now_iso(),
        "stage": stage,
        "message": message,
        "level": level,
        "team": team,
        "task_id": task_id,
        "agent_id": agent_id,
        "agent_role": agent_role,
        "metadata": metadata or {},
    }

    with _lock:
        current = _execution_logs[task_id]
        current.append(entry)
        if len(current) > _MAX_ENTRIES_PER_TASK:
            del current[:-_MAX_ENTRIES_PER_TASK]

    return entry


def get_execution_log(task_id: str) -> list[ExecutionLogEntry]:
    with _lock:
        return list(_execution_logs.get(task_id, []))


def get_last_execution_entry(task_id: str) -> ExecutionLogEntry | None:
    with _lock:
        current = _execution_logs.get(task_id, [])
        return current[-1] if current else None
