"""
AI Office System — Supabase Repository

Camada de acesso a dados sobre o Supabase.  Todos os métodos são
assíncronos e levantam exceções explícitas em caso de falha para que os
chamadores possam tratar erros de persistência sem silenciá-los.

Tabelas gerenciadas:
  tasks         — estado durável de cada tarefa orquestrada pelo LangGraph
  agent_events  — log auditável de todos os eventos gerados pelos agentes
  agent_states  — snapshot do status de cada agente (atualizado em tempo real)
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from supabase import Client

from backend.core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Retorna timestamp ISO 8601 UTC com timezone explícito."""
    return datetime.now(timezone.utc).isoformat()


class SupabaseRepository:
    """
    Repositório de persistência durável via Supabase (PostgreSQL gerenciado).

    Instancia o cliente Supabase na primeira chamada que o requeira.
    Pode ser usado como singleton ou instanciado por request — o cliente
    subjacente já é singleton e thread-safe.
    """

    def __init__(self) -> None:
        self._client: Optional[Client] = None

    async def _get_client(self) -> Client:
        if self._client is None:
            self._client = await get_supabase_client()
        return self._client

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    async def save_task(self, task_state: dict) -> str:
        """
        Persiste uma nova tarefa na tabela `tasks`.

        Aceita um TaskState (dict) do LangGraph.  Caso `task_id` não
        esteja presente no dicionário, gera um UUID v4 novo.

        Returns:
            task_id (str) — identificador UUID da tarefa inserida.

        Raises:
            RuntimeError: Se a inserção falhar no Supabase.
        """
        client = await self._get_client()

        task_id: str = task_state.get("task_id") or str(uuid.uuid4())
        now = _now_iso()

        row = {
            "task_id": task_id,
            "team": task_state.get("team", ""),
            "status": task_state.get("status", "queued"),
            "request": task_state.get("original_request", task_state.get("request", "")),
            "senior_directive": task_state.get("senior_directive"),
            "subtasks": task_state.get("subtasks", []),
            "agent_outputs": task_state.get("agent_outputs", {}),
            "final_output": task_state.get("final_output"),
            "error_count": len(task_state.get("errors", [])),
            "retry_count": task_state.get("retry_count", 0),
            "created_at": now,
            "updated_at": now,
        }

        response = client.table("tasks").insert(row).execute()

        if not response.data:
            raise RuntimeError(
                f"save_task: inserção falhou para task_id={task_id}. "
                f"Resposta: {response}"
            )

        logger.info("[SupabaseRepo] Tarefa salva: task_id=%s team=%s", task_id, row["team"])
        return task_id

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        output: Optional[str] = None,
    ) -> None:
        """
        Atualiza `status`, `final_output` e `updated_at` de uma tarefa.

        Args:
            task_id : UUID da tarefa a atualizar.
            status  : Novo status ("queued" | "running" | "completed" | "failed").
            output  : Texto de saída final (opcional — sobrescreve se fornecido).

        Raises:
            RuntimeError: Se nenhuma linha for afetada (task_id inexistente).
        """
        client = await self._get_client()

        patch: dict = {
            "status": status,
            "updated_at": _now_iso(),
        }
        if output is not None:
            patch["final_output"] = output

        response = (
            client.table("tasks")
            .update(patch)
            .eq("task_id", task_id)
            .execute()
        )

        if not response.data:
            raise RuntimeError(
                f"update_task_status: task_id={task_id} não encontrado ou update falhou."
            )

        logger.debug(
            "[SupabaseRepo] Task atualizada: task_id=%s status=%s", task_id, status
        )

    # ------------------------------------------------------------------
    # Agent Events
    # ------------------------------------------------------------------

    async def save_agent_event(self, event: dict) -> None:
        """
        Persiste um evento de agente na tabela `agent_events`.

        O dicionário `event` é o mesmo produzido por `OfficialEvent.to_dict()`
        (ver event_types.py).  Campos ausentes recebem valores padrão seguros.

        Args:
            event: Dicionário com os campos do evento.

        Raises:
            RuntimeError: Se a inserção falhar.
        """
        client = await self._get_client()

        event_id: str = event.get("event_id") or str(uuid.uuid4())

        # task_id pode ser None em eventos de sistema (ex.: SYSTEM_READY)
        raw_task_id = event.get("task_id")
        task_id: Optional[str] = raw_task_id if raw_task_id else None

        row = {
            "event_id": event_id,
            "event_type": event.get("event_type", "UNKNOWN"),
            "team": event.get("team", "system"),
            "agent_id": event.get("agent_id", "system"),
            "agent_role": event.get("agent_role", "system"),
            "task_id": task_id,
            "payload": event.get("payload", {}),
            "timestamp": event.get("timestamp") or _now_iso(),
        }

        response = client.table("agent_events").insert(row).execute()

        if not response.data:
            raise RuntimeError(
                f"save_agent_event: inserção falhou para event_id={event_id}. "
                f"Resposta: {response}"
            )

        logger.debug(
            "[SupabaseRepo] Evento salvo: event_type=%s task_id=%s",
            row["event_type"],
            task_id,
        )

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    async def get_task(self, task_id: str) -> Optional[dict]:
        """
        Retorna a tarefa pelo UUID ou None se não existir.

        Args:
            task_id: UUID da tarefa.

        Returns:
            Dict com os campos da tarefa ou None.
        """
        client = await self._get_client()

        response = (
            client.table("tasks")
            .select("*")
            .eq("task_id", task_id)
            .limit(1)
            .execute()
        )

        if response.data:
            return response.data[0]
        return None

    async def list_tasks(
        self,
        team: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Lista tarefas em ordem decrescente de criação.

        Args:
            team  : Filtra por equipe ("dev" | "marketing"). None = todas.
            limit : Número máximo de registros retornados (padrão 50).

        Returns:
            Lista de dicts, possivelmente vazia.
        """
        client = await self._get_client()

        query = (
            client.table("tasks")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )

        if team:
            query = query.eq("team", team)

        response = query.execute()
        return response.data or []

    async def get_agent_events(self, task_id: str) -> list[dict]:
        """
        Retorna todos os eventos associados a uma tarefa, ordenados por timestamp ASC.

        Args:
            task_id: UUID da tarefa.

        Returns:
            Lista de eventos (dicts), possivelmente vazia.
        """
        client = await self._get_client()

        response = (
            client.table("agent_events")
            .select("*")
            .eq("task_id", task_id)
            .order("timestamp", desc=False)
            .execute()
        )

        return response.data or []

    # ------------------------------------------------------------------
    # Métricas de sistema
    # ------------------------------------------------------------------

    async def get_system_metrics(self) -> dict:
        """
        Calcula métricas agregadas do sistema consultando a tabela `tasks`.

        Métricas retornadas:
          total_tasks       — total de tarefas registradas
          completed_tasks   — tarefas com status "completed"
          failed_tasks      — tarefas com status "failed"
          avg_duration_ms   — duração média em ms (updated_at - created_at)
          tokens_used       — soma de tokens (campo `tokens_used` se existir, senão 0)

        Returns:
            Dict com as chaves acima.

        Note:
            avg_duration_ms e tokens_used são calculados no lado do cliente
            para manter compatibilidade com qualquer versão do schema.
            Em produção com tabelas grandes, prefira views materializadas
            ou funções RPC no Supabase para melhor performance.
        """
        client = await self._get_client()

        # Busca todos os campos necessários para computar as métricas.
        # Em datasets grandes isso deve ser substituído por uma RPC/função SQL.
        response = (
            client.table("tasks")
            .select("status, created_at, updated_at")
            .execute()
        )

        rows: list[dict] = response.data or []

        total_tasks = len(rows)
        completed_tasks = sum(1 for r in rows if r.get("status") == "completed")
        failed_tasks = sum(1 for r in rows if r.get("status") == "failed")

        # Calcula duração média apenas para tarefas com timestamps válidos
        durations_ms: list[float] = []
        for row in rows:
            try:
                created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                updated = datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
                delta_ms = (updated - created).total_seconds() * 1000
                if delta_ms >= 0:
                    durations_ms.append(delta_ms)
            except (KeyError, ValueError, AttributeError):
                continue

        avg_duration_ms: float = (
            sum(durations_ms) / len(durations_ms) if durations_ms else 0.0
        )

        # tokens_used: soma o campo se existir no schema futuro
        tokens_used: int = 0

        metrics = {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "avg_duration_ms": round(avg_duration_ms, 2),
            "tokens_used": tokens_used,
        }

        logger.debug("[SupabaseRepo] Métricas calculadas: %s", metrics)
        return metrics


# ---------------------------------------------------------------------------
# Instância global — pode ser importada diretamente pelos orquestradores
# ---------------------------------------------------------------------------

supabase_repository = SupabaseRepository()
