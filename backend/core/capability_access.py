"""
Governed access broker for agent Web, directory and screen capabilities.

Agents do not receive unrestricted local powers. They request a scoped grant,
the platform records the risk, and operators approve or reject the request.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


_ROOT = Path(__file__).resolve().parents[2]
_STORE_PATH = _ROOT / ".runtime" / "capability-access" / "requests.json"
_VALID_RESOURCE_TYPES = {"web", "directory", "screen"}
_VALID_ACCESS_LEVELS = {"read", "write", "execute", "control"}
_VALID_STATUSES = {"pending", "approved", "rejected", "expired"}
_MAX_DURATION_MINUTES = 240


@dataclass
class CapabilityAccessRequest:
    request_id: str
    agent_id: str
    agent_role: str
    task_id: str
    resource_type: str
    resource: str
    access_level: str
    reason: str
    status: str
    risk: str
    requires_human_approval: bool
    requested_at: str
    expires_at: str
    approved_by: str = ""
    approved_at: str = ""
    rejected_by: str = ""
    rejected_at: str = ""
    rejection_reason: str = ""
    policy_notes: list[str] = field(default_factory=list)
    normalized_resource: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_capability_request(
    *,
    agent_id: str,
    agent_role: str,
    resource_type: str,
    resource: str,
    access_level: str,
    reason: str,
    task_id: str = "",
    duration_minutes: int = 60,
) -> dict[str, Any]:
    resource_type = _normalize(resource_type)
    access_level = _normalize(access_level)
    duration = max(1, min(int(duration_minutes or 60), _MAX_DURATION_MINUTES))
    notes = _validate_request(resource_type, resource, access_level, reason)
    normalized_resource = _normalize_resource(resource_type, resource)
    risk = _classify_risk(resource_type, access_level, normalized_resource)
    now = _now()
    item = CapabilityAccessRequest(
        request_id=str(uuid.uuid4()),
        agent_id=agent_id.strip(),
        agent_role=_normalize(agent_role),
        task_id=task_id.strip(),
        resource_type=resource_type,
        resource=resource.strip(),
        access_level=access_level,
        reason=reason.strip(),
        status="pending",
        risk=risk,
        requires_human_approval=_requires_human_approval(resource_type, access_level, risk),
        requested_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=duration)).isoformat(),
        policy_notes=notes,
        normalized_resource=normalized_resource,
    )
    records = _load_records()
    records.append(item.to_dict())
    _write_records(records)
    return item.to_dict()


def list_capability_requests(
    *,
    status: str | None = None,
    agent_id: str | None = None,
    include_expired: bool = True,
) -> dict[str, Any]:
    records = [_refresh_expiration(item) for item in _load_records()]
    _write_records(records)
    filtered = records
    if status:
        status_key = _normalize(status)
        filtered = [item for item in filtered if item.get("status") == status_key]
    if agent_id:
        filtered = [item for item in filtered if item.get("agent_id") == agent_id]
    if not include_expired:
        filtered = [item for item in filtered if item.get("status") != "expired"]
    filtered.sort(key=lambda item: str(item.get("requested_at") or ""), reverse=True)
    return {
        "items": filtered,
        "total": len(filtered),
        "summary": _summary(records),
    }


def approve_capability_request(request_id: str, *, approved_by: str = "operator") -> dict[str, Any]:
    records = [_refresh_expiration(item) for item in _load_records()]
    item = _find_record(records, request_id)
    if item["status"] != "pending":
        raise ValueError(f"Capability request is not pending: {item['status']}")
    now = _now().isoformat()
    item["status"] = "approved"
    item["approved_by"] = approved_by.strip() or "operator"
    item["approved_at"] = now
    _write_records(records)
    return item


def reject_capability_request(
    request_id: str,
    *,
    rejected_by: str = "operator",
    reason: str = "",
) -> dict[str, Any]:
    records = [_refresh_expiration(item) for item in _load_records()]
    item = _find_record(records, request_id)
    if item["status"] != "pending":
        raise ValueError(f"Capability request is not pending: {item['status']}")
    now = _now().isoformat()
    item["status"] = "rejected"
    item["rejected_by"] = rejected_by.strip() or "operator"
    item["rejected_at"] = now
    item["rejection_reason"] = reason.strip()
    _write_records(records)
    return item


def get_agent_access_profile(agent_id: str, *, agent_role: str = "") -> dict[str, Any]:
    records = list_capability_requests(agent_id=agent_id, include_expired=False)["items"]
    active = [item for item in records if item.get("status") == "approved"]
    pending = [item for item in records if item.get("status") == "pending"]
    return {
        "agent_id": agent_id,
        "agent_role": _normalize(agent_role),
        "active_grants": active,
        "pending_requests": pending,
        "can_use_web": any(item["resource_type"] == "web" for item in active),
        "can_read_directory": any(
            item["resource_type"] == "directory" and item["access_level"] in {"read", "write", "execute"}
            for item in active
        ),
        "can_write_directory": any(
            item["resource_type"] == "directory" and item["access_level"] in {"write", "execute"}
            for item in active
        ),
        "can_control_screen": any(
            item["resource_type"] == "screen" and item["access_level"] == "control"
            for item in active
        ),
        "rules": [
            "Toda capacidade sensivel precisa de request_id aprovado e ainda vigente.",
            "Controle de tela sempre exige aprovacao humana explicita.",
            "Escrita/execucao em diretorios e risco alto exigem aprovacao humana.",
            "A entrega continua bloqueada pelo Delivery Supervisor Gate sem evidencia e commit.",
        ],
    }


def build_capability_access_policy() -> dict[str, Any]:
    return {
        "resource_types": sorted(_VALID_RESOURCE_TYPES),
        "access_levels": sorted(_VALID_ACCESS_LEVELS),
        "max_duration_minutes": _MAX_DURATION_MINUTES,
        "default_status": "pending",
        "human_approval_required_for": [
            "screen.control",
            "directory.write",
            "directory.execute",
            "high_risk_external_resource",
        ],
        "recommended_plugins": {
            "web": ["browser-use", "Playwright", "GitHub/HuggingFace connectors"],
            "directory": ["filesystem MCP", "PicoClaw filesystem"],
            "screen": ["browser-use first", "desktop control only after explicit approval"],
        },
    }


def _validate_request(resource_type: str, resource: str, access_level: str, reason: str) -> list[str]:
    if resource_type not in _VALID_RESOURCE_TYPES:
        raise ValueError(f"Invalid resource_type: {resource_type}")
    if access_level not in _VALID_ACCESS_LEVELS:
        raise ValueError(f"Invalid access_level: {access_level}")
    if not resource.strip():
        raise ValueError("resource is required")
    if len(reason.strip()) < 10:
        raise ValueError("reason must explain the delivery need")
    if resource_type == "web" and access_level not in {"read", "control"}:
        raise ValueError("web access supports read or control")
    if resource_type == "screen" and access_level != "control":
        raise ValueError("screen access only supports control")
    if resource_type == "directory" and access_level == "control":
        raise ValueError("directory access supports read, write or execute")

    notes = []
    if resource_type == "directory":
        path = Path(resource).expanduser()
        if not path.exists():
            notes.append("directory_path_does_not_exist_yet")
    return notes


def _normalize_resource(resource_type: str, resource: str) -> str:
    raw = resource.strip()
    if resource_type == "web":
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        return parsed.geturl()
    if resource_type == "screen":
        return raw.lower()
    try:
        return str(Path(raw).expanduser().resolve())
    except Exception:
        return raw


def _classify_risk(resource_type: str, access_level: str, normalized_resource: str) -> str:
    if resource_type == "screen":
        return "critical"
    if resource_type == "directory":
        if access_level == "execute":
            return "critical"
        if access_level == "write":
            return "high"
        return "controlled"
    if resource_type == "web":
        parsed = urlparse(normalized_resource)
        host = (parsed.hostname or "").lower()
        if access_level == "control":
            return "high"
        if host in {"localhost", "127.0.0.1", "::1"}:
            return "safe"
        return "controlled"
    return "unknown"


def _requires_human_approval(resource_type: str, access_level: str, risk: str) -> bool:
    return resource_type == "screen" or access_level in {"write", "execute", "control"} or risk in {"high", "critical"}


def _load_records() -> list[dict[str, Any]]:
    if not _STORE_PATH.exists():
        return []
    try:
        raw = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _write_records(records: list[dict[str, Any]]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(records, ensure_ascii=True, indent=2), encoding="utf-8")


def _find_record(records: list[dict[str, Any]], request_id: str) -> dict[str, Any]:
    for item in records:
        if item.get("request_id") == request_id:
            return item
    raise KeyError(request_id)


def _refresh_expiration(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("status") not in _VALID_STATUSES:
        item["status"] = "pending"
    if item.get("status") in {"pending", "approved"} and _is_expired(str(item.get("expires_at") or "")):
        item["status"] = "expired"
    return item


def _is_expired(value: str) -> bool:
    try:
        expires_at = datetime.fromisoformat(value)
    except Exception:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= _now()


def _summary(records: list[dict[str, Any]]) -> dict[str, int]:
    return {status: sum(1 for item in records if item.get("status") == status) for status in sorted(_VALID_STATUSES)}


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


def _now() -> datetime:
    return datetime.now(timezone.utc)
