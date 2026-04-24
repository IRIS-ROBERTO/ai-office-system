"""
Delivery audit aggregation for IRIS.

Reads deterministic delivery manifests and turns them into an executive-grade
audit view: task, agent, commit, gate status, functional readiness, and project
paths. This keeps evidence visible after in-memory task state is gone.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.gold_standard import GENERATED_PROJECTS_ROOT

_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_ROOT = _ROOT / ".runtime" / "delivery-manifests"


def list_delivery_audits(
    *,
    limit: int = 50,
    approved: bool | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    items = _load_manifest_summaries(task_id=task_id)
    if approved is not None:
        items = [item for item in items if item["approved"] is approved]

    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    limited = items[: max(1, min(limit, 250))]

    return {
        "total": len(items),
        "returned": len(limited),
        "approved": sum(1 for item in items if item["approved"]),
        "failed": sum(1 for item in items if not item["approved"]),
        "functional_ready": sum(1 for item in items if item["functional_ready"]),
        "items": limited,
    }


def get_task_delivery_audit(task_id: str) -> dict[str, Any]:
    items = _load_manifest_summaries(task_id=task_id)
    if not items:
        raise FileNotFoundError(task_id)

    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return {
        "task_id": task_id,
        "total": len(items),
        "approved": sum(1 for item in items if item["approved"]),
        "failed": sum(1 for item in items if not item["approved"]),
        "functional_ready": sum(1 for item in items if item["functional_ready"]),
        "commits": [
            {
                "sha": item["commit_sha"],
                "message": item["commit_message"],
                "repo_path": item["repo_path"],
                "pushed": item["pushed"],
            }
            for item in items
            if item["commit_sha"]
        ],
        "items": items,
    }


def get_delivery_track_metrics() -> dict[str, Any]:
    items = _load_manifest_summaries()
    tracks = {
        "platform": _empty_track_metrics(),
        "standalone": _empty_track_metrics(),
    }

    for item in items:
        track = _delivery_track_for_repo(item.get("repo_path", ""))
        bucket = tracks[track]
        bucket["total"] += 1
        if item["approved"]:
            bucket["approved"] += 1
        else:
            bucket["failed"] += 1
        if item["functional_ready"]:
            bucket["functional_ready"] += 1
        if item.get("pushed"):
            bucket["pushed"] += 1

    for bucket in tracks.values():
        total = bucket["total"] or 1
        bucket["approval_rate"] = round(bucket["approved"] / total * 100, 1) if bucket["total"] else 0.0
        bucket["push_rate"] = round(bucket["pushed"] / total * 100, 1) if bucket["total"] else 0.0
    return tracks


def _load_manifest_summaries(*, task_id: str | None = None) -> list[dict[str, Any]]:
    if not _MANIFEST_ROOT.exists():
        return []

    task_dirs = [_MANIFEST_ROOT / task_id] if task_id else [
        path for path in _MANIFEST_ROOT.iterdir() if path.is_dir()
    ]

    summaries: list[dict[str, Any]] = []
    for task_dir in task_dirs:
        if not task_dir.exists() or not task_dir.is_dir():
            continue
        for manifest_path in sorted(task_dir.glob("*.json")):
            manifest = _read_json(manifest_path)
            if not manifest:
                continue
            summaries.append(_summarize_manifest(manifest, manifest_path))
    return summaries


def _summarize_manifest(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    stages = manifest.get("stages") or []
    evidence = manifest.get("evidence") or {}
    failed_stages = [
        stage.get("name", "UNKNOWN")
        for stage in stages
        if stage.get("required", True) and stage.get("status") != "passed"
    ]
    functional_stage = next(
        (stage for stage in stages if stage.get("name") == "FUNCTIONAL_READINESS"),
        None,
    )

    return {
        "task_id": manifest.get("task_id", ""),
        "subtask_id": manifest.get("subtask_id", ""),
        "agent_id": manifest.get("agent_id", ""),
        "agent_role": manifest.get("agent_role", ""),
        "team": manifest.get("team", ""),
        "approved": bool(manifest.get("approved")),
        "feedback": manifest.get("feedback", ""),
        "created_at": manifest.get("created_at", ""),
        "manifest_path": str(manifest_path),
        "failed_stages": failed_stages,
        "stage_count": len(stages),
        "functional_ready": bool(functional_stage and functional_stage.get("status") == "passed"),
        "functional_message": functional_stage.get("message", "") if functional_stage else "",
        "commit_sha": evidence.get("commit_sha", ""),
        "commit_message": evidence.get("commit_message", ""),
        "repo_path": evidence.get("repo_path", ""),
        "delivery_track": _delivery_track_for_repo(evidence.get("repo_path", "")),
        "files_changed": evidence.get("files_changed") or [],
        "pushed": evidence.get("pushed"),
        "stages": [
            {
                "name": stage.get("name", ""),
                "status": stage.get("status", ""),
                "required": bool(stage.get("required", True)),
                "message": stage.get("message", ""),
            }
            for stage in stages
        ],
    }


def _delivery_track_for_repo(repo_path: str) -> str:
    if not repo_path:
        return "platform"
    try:
        candidate = Path(repo_path).expanduser().resolve()
        candidate.relative_to(GENERATED_PROJECTS_ROOT.resolve())
        return "standalone"
    except Exception:
        return "platform"


def _empty_track_metrics() -> dict[str, Any]:
    return {
        "total": 0,
        "approved": 0,
        "failed": 0,
        "functional_ready": 0,
        "pushed": 0,
        "approval_rate": 0.0,
        "push_rate": 0.0,
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
