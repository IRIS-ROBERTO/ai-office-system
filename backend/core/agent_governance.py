"""
Institutional governance model for IRIS agent deliveries.

The policy is inspired by edict's separation of duties: each delivery moves
through explicit institutional phases, and each agent role receives only the
actions needed for its responsibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


POLICY_VERSION = "2026.04.27-edict-institutional-governance"

GOVERNANCE_STATES: tuple[str, ...] = (
    "intake",
    "triage",
    "planning",
    "review",
    "dispatch",
    "execution",
    "validation",
    "archive",
)

GOVERNANCE_TRANSITIONS: tuple[tuple[str, str], ...] = (
    ("intake", "triage"),
    ("triage", "planning"),
    ("planning", "review"),
    ("review", "planning"),
    ("review", "dispatch"),
    ("dispatch", "execution"),
    ("execution", "validation"),
    ("validation", "execution"),
    ("validation", "archive"),
)

GOVERNANCE_ACTIONS: tuple[str, ...] = (
    "triage",
    "plan",
    "review",
    "dispatch",
    "execute",
    "validate",
    "audit",
    "commit",
    "create_dedicated_repo",
)

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "orchestrator": ("triage", "plan", "review", "dispatch", "validate", "audit", "commit"),
    "planner": ("plan", "review", "audit"),
    "backend": ("execute", "validate", "commit"),
    "frontend": ("execute", "validate", "commit"),
    "qa": ("review", "validate", "audit"),
    "security": ("review", "validate", "audit"),
    "docs": ("execute", "audit", "commit"),
    "research": ("triage", "plan", "audit"),
    "scout": ("triage", "plan", "audit"),
    "strategy": ("triage", "plan", "review", "audit"),
    "content": ("execute", "validate", "commit"),
    "seo": ("triage", "execute", "validate"),
    "social": ("execute", "validate"),
    "analytics": ("triage", "review", "validate", "audit"),
    "product_factory": ("triage", "plan", "execute", "validate", "commit", "create_dedicated_repo"),
}


@dataclass(frozen=True)
class GovernanceTransition:
    from_state: str
    to_state: str
    reversible: bool
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_state": self.from_state,
            "to_state": self.to_state,
            "reversible": self.reversible,
            "purpose": self.purpose,
        }


TRANSITION_DETAILS: tuple[GovernanceTransition, ...] = (
    GovernanceTransition("intake", "triage", False, "Registrar demanda e qualificar tipo de entrega."),
    GovernanceTransition("triage", "planning", False, "Converter demanda em escopo tecnico e comercial."),
    GovernanceTransition("planning", "review", False, "Submeter plano a revisao antes da execucao."),
    GovernanceTransition("review", "planning", True, "Devolver plano fraco para refinamento."),
    GovernanceTransition("review", "dispatch", False, "Aprovar plano e liberar despacho controlado."),
    GovernanceTransition("dispatch", "execution", False, "Enviar subtarefas a agentes especialistas."),
    GovernanceTransition("execution", "validation", False, "Exigir evidencia, testes e manifestos."),
    GovernanceTransition("validation", "execution", True, "Bloquear entrega e retornar para retrabalho."),
    GovernanceTransition("validation", "archive", False, "Arquivar entrega aprovada com rastreabilidade."),
)


def normalize_key(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


def list_governance_states() -> list[str]:
    return list(GOVERNANCE_STATES)


def list_governance_transitions() -> list[dict[str, Any]]:
    return [transition.to_dict() for transition in TRANSITION_DETAILS]


def can_transition(from_state: str, to_state: str) -> bool:
    return (normalize_key(from_state), normalize_key(to_state)) in GOVERNANCE_TRANSITIONS


def assert_valid_transition(from_state: str, to_state: str) -> None:
    source = normalize_key(from_state)
    target = normalize_key(to_state)
    if source not in GOVERNANCE_STATES:
        raise ValueError(f"Unknown governance state: {from_state}")
    if target not in GOVERNANCE_STATES:
        raise ValueError(f"Unknown governance state: {to_state}")
    if not can_transition(source, target):
        raise ValueError(f"Invalid governance transition: {source} -> {target}")


def get_role_permissions(role: str) -> dict[str, Any]:
    role_key = normalize_key(role)
    allowed = set(ROLE_PERMISSIONS.get(role_key, ()))
    return {
        "role": role_key,
        "permissions": sorted(allowed),
        "denied": [action for action in GOVERNANCE_ACTIONS if action not in allowed],
        "can_create_dedicated_repo": "create_dedicated_repo" in allowed,
        "can_commit": "commit" in allowed,
    }


def list_governance_permissions() -> dict[str, Any]:
    return {
        "actions": list(GOVERNANCE_ACTIONS),
        "roles": {role: get_role_permissions(role) for role in sorted(ROLE_PERMISSIONS)},
    }


def build_governance_policy() -> dict[str, Any]:
    return {
        "policy_version": POLICY_VERSION,
        "inspiration": "edict: institutional separation of multi-agent duties",
        "delivery_contract": {
            "platform_improvement": "Commit exclusivo no repositorio principal da plataforma.",
            "new_product": "Repositorio dedicado apos validacao de produto e confirmacao de sucesso.",
            "approval_rule": "Nenhuma entrega passa sem evidencia, testes e transicao validation -> archive.",
        },
        "states": list_governance_states(),
        "transitions": list_governance_transitions(),
        "permissions": list_governance_permissions(),
    }


def build_governance_status() -> dict[str, Any]:
    return {
        "status": "active",
        "policy_version": POLICY_VERSION,
        "state_count": len(GOVERNANCE_STATES),
        "transition_count": len(GOVERNANCE_TRANSITIONS),
        "role_count": len(ROLE_PERMISSIONS),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "runtime_guards": [
            "invalid_transition_blocking",
            "role_permission_matrix",
            "platform_vs_product_delivery_contract",
            "validation_before_archive",
        ],
    }
