"""
Autonomy policy based on the Delivery Ledger.

Agents only qualify for autonomous operation when their audited delivery
history demonstrates premium execution, traceability and remote evidence.
"""
from __future__ import annotations

from typing import Any

from backend.core.delivery_ledger import get_delivery_ledger


MIN_DELIVERIES = 3
MIN_PREMIUM_SCORE = 85.0
MIN_APPROVAL_RATE = 90.0
MIN_GITHUB_PUSH_RATE = 95.0
MIN_COMMIT_TRACEABILITY_RATE = 95.0
MIN_FUNCTIONAL_RATE = 80.0
FUNCTIONAL_ROLES = {"frontend", "qa"}


def build_autonomy_policy(agent: dict[str, Any] | None = None) -> dict[str, Any]:
    ledger = get_delivery_ledger(limit=250)
    policies = [_policy_for_row(row) for row in ledger.get("agents") or []]
    policies.sort(key=lambda item: (item["eligible_for_autonomous"], item["premium_score"]), reverse=True)

    payload = {
        "thresholds": {
            "min_deliveries": MIN_DELIVERIES,
            "min_premium_score": MIN_PREMIUM_SCORE,
            "min_approval_rate": MIN_APPROVAL_RATE,
            "min_github_push_rate": MIN_GITHUB_PUSH_RATE,
            "min_commit_traceability_rate": MIN_COMMIT_TRACEABILITY_RATE,
            "min_functional_rate": MIN_FUNCTIONAL_RATE,
            "functional_roles": sorted(FUNCTIONAL_ROLES),
        },
        "eligible_agents": sum(1 for item in policies if item["eligible_for_autonomous"]),
        "blocked_agents": sum(1 for item in policies if not item["eligible_for_autonomous"]),
        "agents": policies,
    }

    if agent is not None:
        payload["agent"] = get_agent_autonomy_policy(agent, ledger=ledger)
    return payload


def get_agent_autonomy_policy(agent: dict[str, Any], *, ledger: dict[str, Any] | None = None) -> dict[str, Any]:
    ledger = ledger or get_delivery_ledger(limit=250)
    agent_id = str(agent.get("agent_id") or "")
    agent_role = str(agent.get("agent_role") or "").lower()
    row = next(
        (
            item for item in ledger.get("agents") or []
            if item.get("agent_id") == agent_id
            or str(item.get("agent_role") or "").lower() == agent_role
        ),
        None,
    )
    if not row:
        return {
            "agent_id": agent_id,
            "agent_role": agent_role,
            "team": agent.get("team", ""),
            "eligible_for_autonomous": False,
            "maturity_level": "no_baseline",
            "premium_score": 0.0,
            "blockers": ["Sem baseline auditado no Delivery Ledger."],
            "next_actions": ["Executar pelo menos 3 entregas com commit, validacao e push confirmados."],
        }
    return _policy_for_row(row)


def assert_autonomous_allowed(agent: dict[str, Any]) -> dict[str, Any]:
    policy = get_agent_autonomy_policy(agent)
    if not policy["eligible_for_autonomous"]:
        blockers = "; ".join(policy["blockers"])
        raise ValueError(f"Autonomia bloqueada pelo Delivery Ledger: {blockers}")
    return policy


def _policy_for_row(row: dict[str, Any]) -> dict[str, Any]:
    role = str(row.get("agent_role") or "").lower()
    blockers: list[str] = []

    if int(row.get("total_deliveries") or 0) < MIN_DELIVERIES:
        blockers.append(f"Menos de {MIN_DELIVERIES} entregas auditadas.")
    if float(row.get("premium_score") or 0.0) < MIN_PREMIUM_SCORE:
        blockers.append(f"Score premium abaixo de {MIN_PREMIUM_SCORE}.")
    if float(row.get("approval_rate") or 0.0) < MIN_APPROVAL_RATE:
        blockers.append(f"Taxa de aprovacao abaixo de {MIN_APPROVAL_RATE}%.")
    if float(row.get("github_push_rate") or 0.0) < MIN_GITHUB_PUSH_RATE:
        blockers.append(f"Push GitHub abaixo de {MIN_GITHUB_PUSH_RATE}%.")
    if float(row.get("commit_traceability_rate") or 0.0) < MIN_COMMIT_TRACEABILITY_RATE:
        blockers.append(f"Rastreabilidade de commit abaixo de {MIN_COMMIT_TRACEABILITY_RATE}%.")
    if _requires_functional_readiness(row, role) and float(row.get("functional_rate") or 0.0) < MIN_FUNCTIONAL_RATE:
        blockers.append(f"Prontidao funcional abaixo de {MIN_FUNCTIONAL_RATE}%.")

    eligible = not blockers
    next_actions = list(row.get("next_actions") or [])
    if blockers and not next_actions:
        next_actions = ["Melhorar entregas ate cumprir todos os thresholds de autonomia."]

    return {
        "agent_id": row.get("agent_id", ""),
        "agent_role": row.get("agent_role", ""),
        "team": row.get("team", ""),
        "eligible_for_autonomous": eligible,
        "maturity_level": "phd" if eligible and float(row.get("premium_score") or 0.0) >= 95 else row.get("maturity_level", ""),
        "premium_score": row.get("premium_score", 0.0),
        "total_deliveries": row.get("total_deliveries", 0),
        "approval_rate": row.get("approval_rate", 0.0),
        "functional_rate": row.get("functional_rate", 0.0),
        "github_push_rate": row.get("github_push_rate", 0.0),
        "commit_traceability_rate": row.get("commit_traceability_rate", 0.0),
        "blockers": blockers,
        "next_actions": next_actions,
    }


def _requires_functional_readiness(row: dict[str, Any], role: str) -> bool:
    classes = row.get("delivery_classes") or {}
    return role in FUNCTIONAL_ROLES or int(classes.get("static_web_app") or 0) > 0
