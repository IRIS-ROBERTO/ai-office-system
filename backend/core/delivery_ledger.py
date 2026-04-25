"""
Delivery Ledger for agent production quality.

Aggregates persisted delivery manifests into a per-agent executive ledger:
throughput, approval, functional readiness, GitHub evidence and premium score.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.core.delivery_audit import list_delivery_audits


def get_delivery_ledger(*, limit: int = 100) -> dict[str, Any]:
    audit = list_delivery_audits(limit=max(limit, 1))
    items = audit.get("items") or []
    agent_rows = _build_agent_rows(items)
    team_rows = _build_team_rows(agent_rows)

    agent_rows.sort(
        key=lambda item: (
            item["premium_score"],
            item["approved_deliveries"],
            item["total_deliveries"],
        ),
        reverse=True,
    )

    return {
        "total_deliveries": len(items),
        "approved_deliveries": sum(1 for item in items if item.get("approved")),
        "functional_ready": sum(1 for item in items if item.get("functional_ready")),
        "pushed_to_github": sum(1 for item in items if item.get("pushed")),
        "agents": agent_rows,
        "teams": team_rows,
        "recent_deliveries": [_compact_delivery(item) for item in items[:20]],
        "recommendations": _ledger_recommendations(agent_rows, items),
    }


def _build_agent_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        key = str(item.get("agent_id") or item.get("agent_role") or "unknown")
        grouped[key].append(item)

    rows: list[dict[str, Any]] = []
    for agent_key, deliveries in grouped.items():
        total = len(deliveries)
        approved = sum(1 for item in deliveries if item.get("approved"))
        functional = sum(1 for item in deliveries if item.get("functional_ready"))
        pushed = sum(1 for item in deliveries if item.get("pushed"))
        commit_ready = sum(1 for item in deliveries if str(item.get("commit_sha") or "").strip())
        failed_stage_counts: dict[str, int] = {}
        delivery_classes: dict[str, int] = {}

        for item in deliveries:
            delivery_class = _delivery_class(item)
            delivery_classes[delivery_class] = delivery_classes.get(delivery_class, 0) + 1
            for stage in item.get("failed_stages") or []:
                failed_stage_counts[stage] = failed_stage_counts.get(stage, 0) + 1

        rows.append({
            "agent_key": agent_key,
            "agent_id": deliveries[0].get("agent_id", ""),
            "agent_role": deliveries[0].get("agent_role", ""),
            "team": deliveries[0].get("team", ""),
            "total_deliveries": total,
            "approved_deliveries": approved,
            "failed_deliveries": total - approved,
            "functional_ready": functional,
            "pushed_to_github": pushed,
            "commit_ready": commit_ready,
            "approval_rate": _rate(approved, total),
            "functional_rate": _rate(functional, total),
            "github_push_rate": _rate(pushed, total),
            "commit_traceability_rate": _rate(commit_ready, total),
            "premium_score": _premium_agent_score(
                approved=approved,
                functional=functional,
                pushed=pushed,
                commit_ready=commit_ready,
                total=total,
            ),
            "delivery_classes": delivery_classes,
            "failed_stage_counts": failed_stage_counts,
            "last_delivery_at": max(str(item.get("created_at") or "") for item in deliveries),
            "maturity_level": _maturity_level(
                _premium_agent_score(
                    approved=approved,
                    functional=functional,
                    pushed=pushed,
                    commit_ready=commit_ready,
                    total=total,
                )
            ),
            "next_actions": _agent_next_actions(
                total=total,
                approved=approved,
                functional=functional,
                pushed=pushed,
                commit_ready=commit_ready,
                failed_stage_counts=failed_stage_counts,
            ),
        })

    return rows


def _build_team_rows(agent_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in agent_rows:
        grouped[str(row.get("team") or "unknown")].append(row)

    teams: list[dict[str, Any]] = []
    for team, rows in grouped.items():
        total = sum(row["total_deliveries"] for row in rows)
        approved = sum(row["approved_deliveries"] for row in rows)
        functional = sum(row["functional_ready"] for row in rows)
        pushed = sum(row["pushed_to_github"] for row in rows)
        commit_ready = sum(row["commit_ready"] for row in rows)
        teams.append({
            "team": team,
            "agents": len(rows),
            "total_deliveries": total,
            "approval_rate": _rate(approved, total),
            "functional_rate": _rate(functional, total),
            "github_push_rate": _rate(pushed, total),
            "commit_traceability_rate": _rate(commit_ready, total),
            "premium_score": _premium_agent_score(
                approved=approved,
                functional=functional,
                pushed=pushed,
                commit_ready=commit_ready,
                total=total,
            ),
        })
    teams.sort(key=lambda item: item["premium_score"], reverse=True)
    return teams


def _compact_delivery(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": item.get("task_id", ""),
        "subtask_id": item.get("subtask_id", ""),
        "agent_id": item.get("agent_id", ""),
        "agent_role": item.get("agent_role", ""),
        "team": item.get("team", ""),
        "approved": bool(item.get("approved")),
        "functional_ready": bool(item.get("functional_ready")),
        "pushed": bool(item.get("pushed")),
        "commit_sha": item.get("commit_sha", ""),
        "delivery_class": _delivery_class(item),
        "created_at": item.get("created_at", ""),
        "failed_stages": item.get("failed_stages") or [],
    }


def _ledger_recommendations(agent_rows: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return [
            "Executar uma entrega deterministica para gerar baseline real por agente.",
            "Manter commits e manifestos obrigatorios para cada subtask entregue.",
        ]

    recommendations: list[str] = []
    low_score = [row for row in agent_rows if row["premium_score"] < 85]
    if low_score:
        recommendations.append("Revisar agentes abaixo de 85 pontos com foco em evidencia, validacao e push remoto.")
    if any(row["github_push_rate"] < 100 for row in agent_rows):
        recommendations.append("Bloquear conclusao premium quando o push GitHub nao estiver confirmado.")
    if any(row["functional_rate"] < 100 for row in agent_rows):
        recommendations.append("Aumentar smoke tests funcionais antes do commit final.")
    if any(row["commit_traceability_rate"] < 100 for row in agent_rows):
        recommendations.append("Exigir commit_sha verificavel e arquivos declarados em toda entrega.")
    return recommendations or ["Manter o padrao atual: score premium, push e rastreabilidade estao saudaveis."]


def _agent_next_actions(
    *,
    total: int,
    approved: int,
    functional: int,
    pushed: int,
    commit_ready: int,
    failed_stage_counts: dict[str, int],
) -> list[str]:
    actions: list[str] = []
    if approved < total:
        actions.append("Reduzir falhas obrigatorias antes de aceitar novas entregas autonomas.")
    if functional < total:
        actions.append("Adicionar smoke test funcional no fluxo do agente.")
    if pushed < total:
        actions.append("Confirmar push GitHub antes de marcar entrega como premium.")
    if commit_ready < total:
        actions.append("Exigir commit_sha verificavel no bloco de evidencia.")
    if failed_stage_counts:
        top_stage = max(failed_stage_counts.items(), key=lambda item: item[1])[0]
        actions.append(f"Atacar falha recorrente no stage {top_stage}.")
    return actions or ["Pronto para maior autonomia em entregas similares."]


def _premium_agent_score(*, approved: int, functional: int, pushed: int, commit_ready: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(
        (_rate(approved, total) * 0.35)
        + (_rate(functional, total) * 0.25)
        + (_rate(pushed, total) * 0.25)
        + (_rate(commit_ready, total) * 0.15),
        1,
    )


def _maturity_level(score: float) -> str:
    if score >= 95:
        return "phd"
    if score >= 85:
        return "premium"
    if score >= 70:
        return "senior"
    return "needs_coaching"


def _rate(value: int, total: int) -> float:
    return round(value / total * 100, 1) if total else 0.0


def _delivery_class(item: dict[str, Any]) -> str:
    files = {str(path).replace("\\", "/").lower() for path in item.get("files_changed") or []}
    if {"index.html", "src/app.js", "src/styles.css"}.issubset(files):
        return "static_web_app"
    if any(path.startswith("security/") for path in files):
        return "security_or_complex_slice"
    if any(path.startswith("tests/") for path in files):
        return "qa_validation"
    if any(path.startswith("docs/") for path in files):
        return "documented_delivery"
    return "general_delivery"
