"""
Supervisor gate for IRIS agent deliveries.

This gate turns delivery quality into an enforceable contract: agents may claim
success only after the platform verifies evidence, commit, validation and the
correct repository strategy for the delivery type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.delivery_evidence import EvidenceValidationResult
from backend.core.gold_standard import GENERATED_PROJECTS_ROOT


_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SupervisorDecision:
    approved: bool
    delivery_type: str
    repo_strategy: str
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    def to_stage(self) -> dict[str, Any]:
        return {
            "name": "SUPERVISOR_GATE",
            "status": "passed" if self.approved else "failed",
            "message": (
                "Supervisor aprovou a entrega para quality gate."
                if self.approved
                else "Supervisor bloqueou a entrega: " + "; ".join(self.reasons)
            ),
            "required": True,
            "metadata": {
                "delivery_type": self.delivery_type,
                "repo_strategy": self.repo_strategy,
                "checks": self.checks,
                "reasons": self.reasons,
            },
        }


def evaluate_delivery_supervisor(
    *,
    evidence_result: EvidenceValidationResult,
    subtask: dict[str, Any],
    agent_role: str,
    require_commit: bool = True,
) -> SupervisorDecision:
    evidence = evidence_result.evidence
    delivery_type = classify_delivery_type(subtask)
    repo_strategy = "unknown"
    checks: dict[str, bool] = {
        "evidence_approved": evidence_result.approved,
        "has_evidence": evidence is not None,
        "has_validation": bool(evidence and evidence.has_validation),
        "has_commit": bool(evidence and evidence.has_commit),
        "repo_strategy_valid": False,
        "role_repo_permission_valid": False,
    }
    reasons: list[str] = []

    if not evidence_result.approved or evidence is None:
        reasons.append("evidencia deterministica ainda nao aprovada")
        return SupervisorDecision(False, delivery_type, repo_strategy, reasons, checks)

    repo_strategy = classify_repo_strategy(evidence.repo_path)
    if delivery_type == "unspecified":
        delivery_type = "new_product" if repo_strategy == "dedicated_repository" else "platform_improvement"
    checks["repo_strategy_valid"] = _repo_strategy_matches(delivery_type, repo_strategy)
    checks["role_repo_permission_valid"] = _role_can_use_repo_strategy(agent_role, repo_strategy)

    if require_commit and not evidence.has_commit:
        reasons.append("commit obrigatorio ausente")
    if not evidence.has_validation:
        reasons.append("validacao obrigatoria ausente")
    if not checks["repo_strategy_valid"]:
        reasons.append(
            f"estrategia de repositorio incorreta para {delivery_type}: {repo_strategy}"
        )
    if not checks["role_repo_permission_valid"]:
        reasons.append(f"papel {agent_role or 'unknown'} nao pode usar estrategia {repo_strategy}")

    approved = not reasons
    return SupervisorDecision(approved, delivery_type, repo_strategy, reasons, checks)


def classify_delivery_type(subtask: dict[str, Any]) -> str:
    explicit = str(
        subtask.get("delivery_type")
        or subtask.get("project_kind")
        or subtask.get("delivery_mode")
        or ""
    ).strip().lower()
    if explicit in {"new_product", "standalone_product", "dedicated_repository"}:
        return "new_product"
    if explicit in {"platform_improvement", "iris_improvement", "main_repository"}:
        return "platform_improvement"

    source = " ".join(
        str(subtask.get(key) or "")
        for key in ("title", "description", "acceptance_criteria")
    ).lower()
    new_product_markers = (
        "produto novo",
        "new product",
        "novo produto",
        "aplicacao nova",
        "aplicação nova",
        "criar app",
        "repositorio dedicado",
        "repositório dedicado",
        "dedicated repository",
    )
    if any(marker in source for marker in new_product_markers):
        return "new_product"
    platform_markers = (
        "platform_improvement",
        "iris_improvement",
        "melhoria da plataforma",
        "plataforma",
        "repositorio principal",
        "repositório principal",
        "main repo",
        "main repository",
    )
    if any(marker in source for marker in platform_markers):
        return "platform_improvement"
    return "unspecified"


def classify_repo_strategy(repo_path: str) -> str:
    try:
        repo_root = Path(repo_path).expanduser().resolve()
    except Exception:
        return "invalid"

    try:
        repo_root.relative_to(_ROOT.resolve())
        return "main_repository"
    except ValueError:
        pass

    try:
        relative = repo_root.relative_to(GENERATED_PROJECTS_ROOT.resolve())
        if relative.parts and relative.parts[0] != "_system":
            return "dedicated_repository"
        return "reserved_generated_repository"
    except ValueError:
        return "external_repository"


def _repo_strategy_matches(delivery_type: str, repo_strategy: str) -> bool:
    if delivery_type == "new_product":
        return repo_strategy == "dedicated_repository"
    if delivery_type == "platform_improvement":
        return repo_strategy == "main_repository"
    return False


def _role_can_use_repo_strategy(agent_role: str, repo_strategy: str) -> bool:
    role = (agent_role or "").strip().lower()
    if repo_strategy == "main_repository":
        return role in {"orchestrator", "backend", "frontend", "qa", "security", "docs", "planner"}
    if repo_strategy == "dedicated_repository":
        return role in {
            "product_factory",
            "frontend",
            "backend",
            "docs",
            "orchestrator",
            "research",
            "strategy",
            "content",
            "seo",
            "social",
            "analytics",
        }
    return False
