"""
Deterministic retrospective generation for failed delivery manifests.

Turns recurrent manifest failures into structured operational feedback so the
platform can improve without relying on manual post-mortems.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[2]
_RETRO_ROOT = _ROOT / ".runtime" / "delivery-retrospectives"

_STAGE_RULES: dict[str, dict[str, str]] = {
    "AGENT_OUTPUT": {
        "failure_class": "execution_output",
        "probable_cause": "Agente retornou erro, timeout ou output sem substancia executavel.",
        "recommended_action": "Reduzir ambiguidade da subtarefa, limitar escopo e reforcar fallback deterministico.",
    },
    "EVIDENCE_PARSE": {
        "failure_class": "contract_adherence",
        "probable_cause": "Agente ignorou o bloco DELIVERY_EVIDENCE ou respondeu apenas com narrativa.",
        "recommended_action": "Endurecer prompt final do papel e reprovar a tentativa sem retry silencioso.",
    },
    "VALIDATION_VERIFY": {
        "failure_class": "objective_validation",
        "probable_cause": "Entrega nao executou validacao objetiva adequada ao dominio.",
        "recommended_action": "Exigir comando de build, smoke test ou validacao de contrato antes do commit.",
    },
    "COMMIT_VERIFY": {
        "failure_class": "git_traceability",
        "probable_cause": "Nao houve commit verificavel, repo_path valido ou arquivos declarados no commit.",
        "recommended_action": "Forcar repo_path, file_paths exatos e gate de commit antes de aprovar output.",
    },
    "FUNCTIONAL_READINESS": {
        "failure_class": "runtime_readiness",
        "probable_cause": "Artefato web nao ficou funcional, interativo ou com assets consistentes.",
        "recommended_action": "Adicionar verificacao funcional minima e smoke test especifico do frontend.",
    },
}


def write_manifest_retrospective(manifest: dict[str, Any]) -> dict[str, Any]:
    task_id = str(manifest.get("task_id") or "")
    subtask_id = str(manifest.get("subtask_id") or "")
    failed_stages = _failed_required_stages(manifest)

    retrospective = {
        "task_id": task_id,
        "subtask_id": subtask_id,
        "agent_id": manifest.get("agent_id", ""),
        "agent_role": manifest.get("agent_role", ""),
        "team": manifest.get("team", ""),
        "approved": bool(manifest.get("approved")),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "failed_stages": failed_stages,
        "root_failure_class": _root_failure_class(failed_stages),
        "probable_causes": _probable_causes(failed_stages),
        "recommended_actions": _recommended_actions(failed_stages),
        "feedback": manifest.get("feedback", ""),
        "manifest_path": manifest.get("manifest_path", ""),
    }

    retro_path = _retrospective_path(task_id, subtask_id)
    retro_path.parent.mkdir(parents=True, exist_ok=True)
    retro_path.write_text(json.dumps(retrospective, ensure_ascii=True, indent=2), encoding="utf-8")
    retrospective["retrospective_path"] = str(retro_path)
    return retrospective


def list_retrospectives(*, task_id: str | None = None, limit: int = 50) -> dict[str, Any]:
    root = _RETRO_ROOT / task_id if task_id else _RETRO_ROOT
    if not root.exists():
        return {"total": 0, "returned": 0, "items": []}

    if task_id:
        files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    else:
        files = sorted(root.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    items: list[dict[str, Any]] = []
    for path in files[: max(1, min(limit, 200))]:
        try:
            items.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return {"total": len(files), "returned": len(items), "items": items}


def _failed_required_stages(manifest: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    for stage in manifest.get("stages") or []:
        if stage.get("required", True) and stage.get("status") != "passed":
            failed.append(str(stage.get("name") or "UNKNOWN"))
    return failed


def _root_failure_class(failed_stages: list[str]) -> str:
    for stage in failed_stages:
        rule = _STAGE_RULES.get(stage)
        if rule:
            return rule["failure_class"]
    return "approved" if not failed_stages else "unknown"


def _probable_causes(failed_stages: list[str]) -> list[str]:
    causes = []
    for stage in failed_stages:
        rule = _STAGE_RULES.get(stage)
        if rule:
            causes.append(rule["probable_cause"])
    return causes or ["Nenhuma falha obrigatoria detectada."]


def _recommended_actions(failed_stages: list[str]) -> list[str]:
    actions = []
    for stage in failed_stages:
        rule = _STAGE_RULES.get(stage)
        if rule:
            actions.append(rule["recommended_action"])
    return actions or ["Nenhuma acao corretiva obrigatoria."]


def _retrospective_path(task_id: str, subtask_id: str) -> Path:
    safe_task = task_id or "unknown-task"
    safe_subtask = subtask_id or "unknown-subtask"
    return _RETRO_ROOT / safe_task / f"{safe_subtask}.json"
