"""
Governed memory gateway for IRIS agents.

This is the local production-safe memory layer. It stores only sanitized,
auditable records and can later delegate persistence/retrieval to MemOS or
Hermes without changing orchestrator contracts.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from backend.config.settings import settings


_ROOT = Path(__file__).resolve().parents[2]
_MEMORY_ROOT = _ROOT / ".runtime" / "memory-gateway"
_MEMORY_FILE = _MEMORY_ROOT / "memories.jsonl"

MEMORY_CLASSES = {
    "project_memory",
    "agent_skill_memory",
    "failure_memory",
    "decision_memory",
    "user_preference_memory",
    "tool_memory",
}

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"github_pat_[A-Za-z0-9_]+", re.IGNORECASE),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b", re.IGNORECASE),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^'\"\s]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


@dataclass
class MemoryRecord:
    id: str
    memory_class: str
    content: str
    source: str
    source_id: str = ""
    task_id: str = ""
    subtask_id: str = ""
    agent_id: str = ""
    agent_role: str = ""
    project_path: str = ""
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.8
    approved: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryWriteResult:
    stored: bool
    reason: str
    record: MemoryRecord | None = None
    blocked_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stored": self.stored,
            "reason": self.reason,
            "record": self.record.to_dict() if self.record else None,
            "blocked_patterns": self.blocked_patterns,
        }


class MemoryGateway:
    """Append-only local memory store with secret screening and simple retrieval."""

    def status(self) -> dict[str, Any]:
        records = self.list_memories(limit=5000)
        by_class: dict[str, int] = {}
        by_role: dict[str, int] = {}
        for record in records:
            by_class[record.memory_class] = by_class.get(record.memory_class, 0) + 1
            if record.agent_role:
                by_role[record.agent_role] = by_role.get(record.agent_role, 0) + 1
        return {
            "provider": "local_jsonl",
            "storage_path": str(_MEMORY_FILE),
            "total": len(records),
            "by_class": by_class,
            "by_role": by_role,
            "memory_classes": sorted(MEMORY_CLASSES),
            "external_provider": self.external_provider_status(),
            "governance": {
                "secret_screening": True,
                "append_only": True,
                "approval_required_for_agent_writes": True,
                "external_provider": "memos" if settings.MEMOS_ENABLED else "not_configured",
                "external_sync_enabled": bool(settings.MEMORY_EXTERNAL_SYNC_ENABLED),
            },
        }

    def remember(
        self,
        *,
        memory_class: str,
        content: str,
        source: str,
        source_id: str = "",
        task_id: str = "",
        subtask_id: str = "",
        agent_id: str = "",
        agent_role: str = "",
        project_path: str = "",
        tags: list[str] | None = None,
        confidence: float = 0.8,
        approved: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryWriteResult:
        normalized_class = memory_class.strip().lower()
        if normalized_class not in MEMORY_CLASSES:
            return MemoryWriteResult(False, f"memory_class invalida: {memory_class}")
        clean_content = _normalize_content(content)
        if not clean_content:
            return MemoryWriteResult(False, "conteudo vazio")
        blocked = _secret_hits(clean_content)
        if blocked:
            return MemoryWriteResult(
                stored=False,
                reason="memoria bloqueada por possivel segredo",
                blocked_patterns=blocked,
            )
        if not approved and source != "operator_manual":
            return MemoryWriteResult(False, "memoria nao aprovada pelo orquestrador")

        record = MemoryRecord(
            id=_memory_id(normalized_class, clean_content, source_id, task_id, subtask_id),
            memory_class=normalized_class,
            content=clean_content,
            source=source,
            source_id=source_id,
            task_id=task_id,
            subtask_id=subtask_id,
            agent_id=agent_id,
            agent_role=agent_role,
            project_path=project_path,
            tags=sorted({tag.strip().lower() for tag in tags or [] if tag.strip()}),
            confidence=max(0.0, min(1.0, confidence)),
            approved=approved,
            metadata=metadata or {},
        )
        if self._exists(record.id):
            return MemoryWriteResult(False, "memoria duplicada", record)
        external_sync = self._sync_to_memos(record)
        record.metadata["external_sync"] = external_sync
        if external_sync.get("status") == "required_failed":
            return MemoryWriteResult(False, "provedor externo de memoria requerido indisponivel", record)
        self._append(record)
        return MemoryWriteResult(True, "memoria armazenada", record)

    def capture_from_delivery_manifest(self, manifest: dict[str, Any]) -> list[MemoryWriteResult]:
        if not manifest.get("approved"):
            return []
        evidence = manifest.get("evidence") or {}
        if not evidence:
            return []

        agent_role = str(manifest.get("agent_role") or evidence.get("agent_role") or "")
        agent_id = str(manifest.get("agent_id") or evidence.get("agent") or "")
        task_id = str(manifest.get("task_id") or evidence.get("task_id") or "")
        subtask_id = str(manifest.get("subtask_id") or evidence.get("subtask_id") or "")
        repo_path = str(evidence.get("repo_path") or "")
        commit_sha = str(evidence.get("commit_sha") or "")
        commit_message = str(evidence.get("commit_message") or "")
        files = evidence.get("files_changed") or []
        validations = evidence.get("validation") or []
        source_id = str(manifest.get("manifest_path") or f"{task_id}:{subtask_id}")

        project_content = (
            f"Approved delivery by {agent_role or agent_id}: commit {commit_sha} "
            f"({commit_message}). Files changed: {', '.join(files[:12])}. "
            f"Project path: {repo_path}."
        )
        skill_content = (
            f"{agent_role or 'agent'} completed a verified delivery with validations: "
            f"{_validation_summary(validations)}. Reuse this evidence pattern for similar tasks."
        )
        tool_content = (
            f"Delivery gate accepted commit {commit_sha} after validation checks. "
            "Use workspace_file, objective validation and github_commit evidence before approval."
        )

        common = {
            "source": "approved_delivery_manifest",
            "source_id": source_id,
            "task_id": task_id,
            "subtask_id": subtask_id,
            "agent_id": agent_id,
            "agent_role": agent_role,
            "project_path": repo_path,
            "approved": True,
            "metadata": {"commit_sha": commit_sha, "commit_message": commit_message},
        }
        return [
            self.remember(
                memory_class="project_memory",
                content=project_content,
                tags=["delivery", "project", agent_role],
                confidence=0.9,
                **common,
            ),
            self.remember(
                memory_class="agent_skill_memory",
                content=skill_content,
                tags=["skill", "validation", agent_role],
                confidence=0.8,
                **common,
            ),
            self.remember(
                memory_class="tool_memory",
                content=tool_content,
                tags=["tooling", "commit", "delivery-runner"],
                confidence=0.85,
                **common,
            ),
        ]

    def list_memories(
        self,
        *,
        memory_class: str | None = None,
        agent_role: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        records = self._read_all()
        if memory_class:
            records = [record for record in records if record.memory_class == memory_class]
        if agent_role:
            records = [record for record in records if record.agent_role == agent_role]
        records.sort(key=lambda record: record.created_at, reverse=True)
        return records[: max(1, min(limit, 1000))]

    def search(
        self,
        *,
        query: str,
        memory_class: str | None = None,
        agent_role: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        query_terms = _terms(query)
        records = self.list_memories(memory_class=memory_class, agent_role=agent_role, limit=5000)
        scored: list[tuple[float, MemoryRecord]] = []
        for record in records:
            haystack = " ".join([record.content, " ".join(record.tags), record.agent_role])
            score = _score(query_terms, haystack)
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
        return [
            {"score": round(score, 4), "record": record.to_dict()}
            for score, record in scored[: max(1, min(limit, 50))]
        ]

    def search_external(self, *, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not settings.MEMOS_ENABLED:
            return []
        clean_query = _normalize_content(query)
        if not clean_query:
            return []

        payload = {
            "query": clean_query,
            "user_id": settings.MEMOS_USER_ID,
            "mem_cube_id": settings.MEMOS_MEM_CUBE_ID,
            "install_cube": False,
            "top_k": max(1, min(limit, 50)),
        }
        try:
            response = httpx.post(
                f"{_memos_host()}/product/search",
                json=payload,
                timeout=4.0,
            )
            response.raise_for_status()
            body = response.json()
        except Exception:
            return []

        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            return []
        items: list[dict[str, Any]] = []
        for bucket_name in ("text_mem", "act_mem", "para_mem"):
            bucket = data.get(bucket_name) or []
            if not isinstance(bucket, list):
                continue
            for cube in bucket:
                memories = cube.get("memories") if isinstance(cube, dict) else None
                if not isinstance(memories, list):
                    continue
                for memory in memories:
                    if isinstance(memory, dict):
                        items.append({"provider": "memos", "type": bucket_name, "item": memory})
                    if len(items) >= max(1, min(limit, 50)):
                        return items
        return items

    def external_provider_status(self) -> dict[str, Any]:
        base = {
            "provider": "memos",
            "enabled": bool(settings.MEMOS_ENABLED),
            "required": bool(settings.MEMOS_REQUIRED),
            "sync_enabled": bool(settings.MEMORY_EXTERNAL_SYNC_ENABLED),
            "host": _memos_host(),
            "user_id": settings.MEMOS_USER_ID,
            "mem_cube_id": settings.MEMOS_MEM_CUBE_ID,
        }
        if not settings.MEMOS_ENABLED:
            return {**base, "status": "disabled", "reason": "MEMOS_ENABLED=false"}
        try:
            response = httpx.get(f"{_memos_host()}/openapi.json", timeout=3.0)
            if response.status_code < 500:
                return {**base, "status": "online", "http_status": response.status_code}
            return {**base, "status": "degraded", "http_status": response.status_code}
        except Exception as exc:
            return {**base, "status": "offline", "error": str(exc)}

    def _append(self, record: MemoryRecord) -> None:
        _MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
        with _MEMORY_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=True) + "\n")

    def _sync_to_memos(self, record: MemoryRecord) -> dict[str, Any]:
        if not settings.MEMOS_ENABLED:
            return {"provider": "memos", "status": "disabled", "reason": "MEMOS_ENABLED=false"}
        if not settings.MEMORY_EXTERNAL_SYNC_ENABLED:
            return {"provider": "memos", "status": "skipped", "reason": "MEMORY_EXTERNAL_SYNC_ENABLED=false"}

        payload = {
            "user_id": settings.MEMOS_USER_ID,
            "mem_cube_id": settings.MEMOS_MEM_CUBE_ID,
            "messages": [
                {
                    "role": "user",
                    "content": f"[{record.memory_class}] {record.content}",
                },
                {
                    "role": "assistant",
                    "content": "Memory accepted by IRIS MemoryGateway governance.",
                },
            ],
            "memory_content": "",
            "doc_path": "",
            "source": record.source,
            "user_profile": False,
        }
        try:
            response = httpx.post(
                f"{_memos_host()}/product/add",
                json=payload,
                timeout=4.0,
            )
            response.raise_for_status()
            return {
                "provider": "memos",
                "status": "synced",
                "http_status": response.status_code,
            }
        except Exception as exc:
            status = "required_failed" if settings.MEMOS_REQUIRED else "failed_non_blocking"
            return {
                "provider": "memos",
                "status": status,
                "error": str(exc),
            }

    def _exists(self, memory_id: str) -> bool:
        return any(record.id == memory_id for record in self._read_all())

    def _read_all(self) -> list[MemoryRecord]:
        if not _MEMORY_FILE.exists():
            return []
        records: list[MemoryRecord] = []
        for line in _MEMORY_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                records.append(MemoryRecord(**data))
            except Exception:
                continue
        return records


def _memory_id(memory_class: str, content: str, source_id: str, task_id: str, subtask_id: str) -> str:
    raw = "\n".join([memory_class, content, source_id, task_id, subtask_id])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _memos_host() -> str:
    return settings.MEMOS_HOST.rstrip("/")


def _normalize_content(content: str) -> str:
    return re.sub(r"\s+", " ", (content or "").strip())[:4000]


def _secret_hits(content: str) -> list[str]:
    hits: list[str] = []
    for pattern in _SECRET_PATTERNS:
        if pattern.search(content):
            hits.append(pattern.pattern[:80])
    return hits


def _terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[a-zA-Z0-9_/-]{3,}", value.lower())}


def _score(query_terms: set[str], value: str) -> float:
    if not query_terms:
        return 0.0
    value_terms = _terms(value)
    if not value_terms:
        return 0.0
    overlap = query_terms & value_terms
    return len(overlap) / len(query_terms)


def _validation_summary(validations: list[dict[str, Any]]) -> str:
    if not validations:
        return "no validation details"
    parts = []
    for item in validations[:5]:
        parts.append(f"{item.get('command', 'validation')} => {item.get('result', 'unknown')}")
    return "; ".join(parts)


memory_gateway = MemoryGateway()
