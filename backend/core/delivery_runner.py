"""
Deterministic delivery runner for IRIS agent subtasks.

This module does not replace CrewAI execution. It wraps the agent output with a
strict operational manifest so the orchestrator can distinguish:
- agent claimed success;
- platform verified evidence;
- delivery is actually ready for quality review.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.delivery_evidence import (
    EvidenceValidationResult,
    validate_delivery_evidence,
)


_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_ROOT = _ROOT / ".runtime" / "delivery-manifests"


@dataclass
class DeliveryStage:
    name: str
    status: str
    message: str
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "passed"


@dataclass
class DeliveryManifest:
    task_id: str
    subtask_id: str
    agent_id: str
    agent_role: str
    team: str
    approved: bool
    feedback: str
    stages: list[DeliveryStage]
    evidence: dict[str, Any] | None
    output_preview: str
    created_at: str
    manifest_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stages"] = [asdict(stage) for stage in self.stages]
        return data


class DeliveryRunner:
    """Builds and persists deterministic delivery manifests for subtasks."""

    def evaluate_subtask_output(
        self,
        *,
        task_id: str,
        subtask: dict[str, Any],
        output_text: str,
        agent_id: str,
        agent_role: str,
        team: str,
        require_commit: bool = True,
    ) -> DeliveryManifest:
        subtask_id = str(subtask.get("id") or "")
        stages: list[DeliveryStage] = []

        stages.append(self._plan_lock_stage(subtask))
        stages.append(self._agent_output_stage(output_text))

        evidence_result = validate_delivery_evidence(
            output_text,
            task_id=task_id,
            subtask_id=subtask_id,
            require_commit=require_commit,
        )
        stages.extend(self._evidence_stages(evidence_result, require_commit=require_commit))

        required_failures = [
            stage for stage in stages if stage.required and not stage.passed
        ]
        approved = not required_failures
        feedback = (
            "Entrega deterministica aprovada para quality gate."
            if approved
            else "Entrega bloqueada: "
            + "; ".join(f"{stage.name}: {stage.message}" for stage in required_failures)
        )

        manifest = DeliveryManifest(
            task_id=task_id,
            subtask_id=subtask_id,
            agent_id=agent_id,
            agent_role=agent_role,
            team=team,
            approved=approved,
            feedback=feedback,
            stages=stages,
            evidence=evidence_result.evidence.to_dict() if evidence_result.evidence else None,
            output_preview=(output_text or "")[:1200],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        manifest.manifest_path = str(self._manifest_path(manifest.task_id, manifest.subtask_id))
        self._write_manifest(manifest)
        return manifest

    def _plan_lock_stage(self, subtask: dict[str, Any]) -> DeliveryStage:
        missing = [
            key
            for key in ("id", "title", "description", "acceptance_criteria", "assigned_role")
            if not str(subtask.get(key) or "").strip()
        ]
        if missing:
            return DeliveryStage(
                name="PLAN_LOCK",
                status="failed",
                message="Subtarefa sem campos obrigatorios: " + ", ".join(missing),
                metadata={"missing": missing},
            )
        return DeliveryStage(
            name="PLAN_LOCK",
            status="passed",
            message="Escopo, dono e criterio de aceite definidos.",
            metadata={
                "title": subtask.get("title"),
                "assigned_role": subtask.get("assigned_role"),
            },
        )

    def _agent_output_stage(self, output_text: str) -> DeliveryStage:
        output = (output_text or "").strip()
        if not output:
            return DeliveryStage(
                name="AGENT_OUTPUT",
                status="failed",
                message="Agente nao retornou output.",
            )
        lowered = output.lower()
        if lowered.startswith("erro:") or "subtarefa excedeu timeout" in lowered:
            return DeliveryStage(
                name="AGENT_OUTPUT",
                status="failed",
                message=output[:300],
                metadata={"output_length": len(output)},
            )
        return DeliveryStage(
            name="AGENT_OUTPUT",
            status="passed",
            message="Agente retornou output para avaliacao.",
            metadata={"output_length": len(output)},
        )

    def _evidence_stages(
        self,
        evidence_result: EvidenceValidationResult,
        *,
        require_commit: bool,
    ) -> list[DeliveryStage]:
        evidence = evidence_result.evidence
        if evidence is None:
            return [
                DeliveryStage(
                    name="EVIDENCE_PARSE",
                    status="failed",
                    message=evidence_result.feedback,
                ),
                DeliveryStage(
                    name="VALIDATION_VERIFY",
                    status="failed",
                    message="Nao ha validation no DELIVERY_EVIDENCE.",
                ),
                DeliveryStage(
                    name="COMMIT_VERIFY",
                    status="failed" if require_commit else "skipped",
                    message="Nao ha commit verificavel.",
                    required=require_commit,
                ),
            ]

        validation_status = "passed" if evidence.has_validation else "failed"
        commit_status = "passed" if evidence.has_commit else "failed"
        if evidence_result.approved:
            validation_message = "Validacao declarada e aceita pelo gate deterministico."
            commit_message = "Commit existe, contem arquivos declarados e esta dentro da raiz autorizada."
        else:
            validation_message = evidence_result.feedback
            commit_message = evidence_result.feedback

        return [
            DeliveryStage(
                name="EVIDENCE_PARSE",
                status="passed",
                message="DELIVERY_EVIDENCE parseado.",
                metadata={
                    "files_changed": evidence.files_changed,
                    "repo_path": evidence.repo_path,
                },
            ),
            DeliveryStage(
                name="VALIDATION_VERIFY",
                status=validation_status if evidence_result.approved else "failed",
                message=validation_message,
                metadata={"validation": evidence.validation},
            ),
            DeliveryStage(
                name="COMMIT_VERIFY",
                status=commit_status if evidence_result.approved else "failed",
                message=commit_message,
                required=require_commit,
                metadata={
                    "commit_sha": evidence.commit_sha,
                    "commit_message": evidence.commit_message,
                    "pushed": evidence.pushed,
                },
            ),
        ]

    def _manifest_path(self, task_id: str, subtask_id: str) -> Path:
        return _MANIFEST_ROOT / task_id / f"{subtask_id}.json"

    def _write_manifest(self, manifest: DeliveryManifest) -> Path:
        target = self._manifest_path(manifest.task_id, manifest.subtask_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        return target


delivery_runner = DeliveryRunner()
