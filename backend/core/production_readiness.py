"""
Production readiness gate for IRIS.

The gate is intentionally strict: production requires clean evidence, durable
runtime dependencies, and a clean release surface. It does not read secret
values; it only reports configuration/runtime status.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[2]

_LOCAL_ARTIFACT_PREFIXES = (
    ".runtime/",
    "agent-deliveries/",
    "frontend/.claude/",
    "frontend/dist/",
    "logs/",
)
_LOCAL_ARTIFACT_FILES = (
    ".env",
    "frontend/.env.local",
    "tmp-uvicorn-reload.err.log",
    "tmp-uvicorn-reload.out.log",
)


def build_production_readiness_report(
    *,
    health: dict[str, Any],
    delivery_audit: dict[str, Any],
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = (repo_root or _ROOT).resolve()
    git_summary = _git_summary(root)

    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    _require(health.get("api") == "online", blockers, "api_offline", "API nao esta online.")
    _require(health.get("redis") == "online", blockers, "redis_offline", "Redis precisa estar online e persistente.")
    _require(
        bool(health.get("event_bus_persistent")),
        blockers,
        "event_bus_not_persistent",
        "EventBus precisa usar Redis persistente, nao fallback fake/in-memory.",
    )
    _require(health.get("ollama") == "online", blockers, "ollama_offline", "Ollama precisa estar online.")

    picoclaw = health.get("picoclaw") or {}
    if picoclaw.get("status") != "online":
        item = {
            "code": "picoclaw_offline",
            "message": "PicoClaw esta instalado, mas a bridge HTTP nao esta online.",
        }
        if bool(picoclaw.get("required")):
            blockers.append(item)
        else:
            warnings.append(
                {
                    "code": "picoclaw_optional_offline",
                    "message": (
                        "PicoClaw esta indisponivel, mas PICOCLAW_REQUIRED=false; "
                        "agentes seguem sem essa bridge de plugins."
                    ),
                }
            )

    if int(health.get("active_tasks") or 0) > 0:
        warnings.append(
            {
                "code": "active_tasks",
                "message": "Ha tarefas ativas; evite release enquanto agentes executam entregas.",
            }
        )

    approved = int(delivery_audit.get("approved") or 0)
    failed = int(delivery_audit.get("failed") or 0)
    functional_ready = int(delivery_audit.get("functional_ready") or 0)
    total = int(delivery_audit.get("total") or 0)

    if total == 0:
        blockers.append(
            {
                "code": "no_delivery_evidence",
                "message": "Nao ha manifestos de entrega para auditar.",
            }
        )
    if approved == 0:
        blockers.append(
            {
                "code": "no_approved_delivery",
                "message": "Nenhuma entrega aprovada pelo Delivery Runner.",
            }
        )
    if functional_ready == 0:
        blockers.append(
            {
                "code": "no_functional_ready_delivery",
                "message": "Nenhuma entrega passou por FUNCTIONAL_READINESS.",
            }
        )
    if failed > approved:
        warnings.append(
            {
                "code": "delivery_failure_ratio",
                "message": "Ha mais entregas falhas do que aprovadas; investigar antes de operar em producao.",
            }
        )

    if git_summary["dirty"]:
        release_blocker_count = int(git_summary.get("release_blocker_count") or 0)
        blockers.append(
            {
                "code": "dirty_worktree",
                "message": (
                    "Repositorio possui "
                    f"{release_blocker_count} alteracoes de release nao commitadas ou nao rastreadas."
                ),
            }
        )

    score = _score(blockers=blockers, warnings=warnings, delivery_audit=delivery_audit)
    status = "ready" if not blockers else "blocked"

    return {
        "status": status,
        "score": score,
        "production_ready": status == "ready",
        "blockers": blockers,
        "warnings": warnings,
        "runtime": {
            "api": health.get("api"),
            "redis": health.get("redis"),
            "event_bus": health.get("event_bus"),
            "event_bus_persistent": health.get("event_bus_persistent"),
            "ollama": health.get("ollama"),
            "picoclaw_status": picoclaw.get("status"),
            "picoclaw_required": picoclaw.get("required"),
            "active_tasks": health.get("active_tasks"),
        },
        "delivery_audit": {
            "total": total,
            "approved": approved,
            "failed": failed,
            "functional_ready": functional_ready,
        },
        "git": git_summary,
        "next_actions": _next_actions(blockers, warnings),
    }


def _require(condition: bool, blockers: list[dict[str, str]], code: str, message: str) -> None:
    if not condition:
        blockers.append({"code": code, "message": message})


def _git_summary(repo_root: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        return {
            "available": False,
            "dirty": True,
            "changed_count": 0,
            "untracked_count": 0,
            "sample": [],
            "error": (result.stderr or result.stdout or "git status failed").strip(),
        }

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    entries = [_parse_git_status_line(line) for line in lines]
    untracked = [entry for entry in entries if entry["status"] == "??"]
    local_artifacts = [
        entry for entry in entries if _is_local_runtime_artifact(entry["status"], entry["path"])
    ]
    release_blockers = [
        entry for entry in entries if entry not in local_artifacts
    ]

    return {
        "available": True,
        "dirty": bool(release_blockers),
        "changed_count": len(lines),
        "untracked_count": len(untracked),
        "release_blocker_count": len(release_blockers),
        "local_artifact_count": len(local_artifacts),
        "sample": [_sanitize_git_status_line(entry["line"]) for entry in release_blockers[:25]],
        "local_artifacts_sample": [
            _sanitize_git_status_line(entry["line"]) for entry in local_artifacts[:25]
        ],
    }


def _parse_git_status_line(line: str) -> dict[str, str]:
    status = line[:2]
    raw_path = line[3:] if len(line) > 3 else ""
    if " -> " in raw_path:
        raw_path = raw_path.split(" -> ", 1)[1]
    path = raw_path.strip().replace("\\", "/")
    return {"line": line, "status": status, "path": path}


def _is_local_runtime_artifact(status: str, path: str) -> bool:
    if status != "??":
        return False
    if path in _LOCAL_ARTIFACT_FILES:
        return True
    if path.endswith("/.env") or path.endswith("/.env.local"):
        return True
    if path.endswith("__pycache__/") or "/__pycache__/" in path:
        return True
    return any(path.startswith(prefix) for prefix in _LOCAL_ARTIFACT_PREFIXES)


def _sanitize_git_status_line(line: str) -> str:
    # Keep operational visibility without exposing file contents or secret values.
    sensitive_names = (".env.local", ".env")
    for name in sensitive_names:
        if line.strip().endswith(name) or line.strip().endswith(f"/{name}"):
            return line.replace(name, f"{name} (secret file, content not shown)")
    return line


def _score(
    *,
    blockers: list[dict[str, str]],
    warnings: list[dict[str, str]],
    delivery_audit: dict[str, Any],
) -> int:
    score = 100
    score -= len(blockers) * 18
    score -= len(warnings) * 7
    total = max(1, int(delivery_audit.get("total") or 0))
    failed = int(delivery_audit.get("failed") or 0)
    score -= min(20, int((failed / total) * 20))
    return max(0, min(100, score))


def _next_actions(blockers: list[dict[str, str]], warnings: list[dict[str, str]]) -> list[str]:
    actions: list[str] = []
    codes = {item["code"] for item in blockers + warnings}

    if "dirty_worktree" in codes:
        actions.append("Limpar workspace: commitar mudancas intencionais e remover artefatos gerados/cache.")
    if "picoclaw_offline" in codes:
        actions.append("Ativar PicoClaw bridge HTTP ou marcar a integracao como desabilitada para producao.")
    if "picoclaw_optional_offline" in codes:
        actions.append("Concluir ajuste PicoClaw schema v2/gateway antes de depender dele em tarefas criticas.")
    if "redis_offline" in codes or "event_bus_not_persistent" in codes:
        actions.append("Garantir Redis persistente e healthcheck obrigatorio no deploy.")
    if "no_functional_ready_delivery" in codes or "no_approved_delivery" in codes:
        actions.append("Executar uma entrega real ate passar em todos os gates funcionais.")
    if "delivery_failure_ratio" in codes:
        actions.append("Analisar /delivery-audit e corrigir causas recorrentes de falha dos agentes.")
    if not actions:
        actions.append("Executar smoke test de staging e promover somente com o mesmo commit auditado.")
    return actions
