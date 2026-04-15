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
        blockers.append(
            {
                "code": "picoclaw_offline",
                "message": "PicoClaw esta instalado, mas a bridge HTTP nao esta online.",
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
        blockers.append(
            {
                "code": "dirty_worktree",
                "message": "Repositorio possui alteracoes nao commitadas ou arquivos nao rastreados.",
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
    untracked = [line for line in lines if line.startswith("??")]
    return {
        "available": True,
        "dirty": bool(lines),
        "changed_count": len(lines),
        "untracked_count": len(untracked),
        "sample": [_sanitize_git_status_line(line) for line in lines[:25]],
    }


def _sanitize_git_status_line(line: str) -> str:
    # Keep operational visibility without exposing file contents or secret values.
    sensitive_names = (".env", ".env.local")
    for name in sensitive_names:
        if line.strip().endswith(name):
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
    if "redis_offline" in codes or "event_bus_not_persistent" in codes:
        actions.append("Garantir Redis persistente e healthcheck obrigatorio no deploy.")
    if "no_functional_ready_delivery" in codes or "no_approved_delivery" in codes:
        actions.append("Executar uma entrega real ate passar em todos os gates funcionais.")
    if "delivery_failure_ratio" in codes:
        actions.append("Analisar /delivery-audit e corrigir causas recorrentes de falha dos agentes.")
    if not actions:
        actions.append("Executar smoke test de staging e promover somente com o mesmo commit auditado.")
    return actions
