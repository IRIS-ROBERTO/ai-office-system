"""
Runtime gateway registry for agent infrastructure providers.

The production contract is conservative: PicoClaw remains the active MCP bridge
until another provider is installed, reachable, governed and explicitly selected.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

import httpx

from backend.config.settings import settings
from backend.tools.picoclaw_tool import check_picoclaw_health


@dataclass(frozen=True)
class RuntimeProvider:
    name: str
    role: str
    enabled: bool
    required: bool
    host: str
    maturity: str
    purpose: str
    replacement_ready: bool
    risks: tuple[str, ...]
    recommended_next_step: str

    def to_dict(self, status: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "enabled": self.enabled,
            "required": self.required,
            "host": self.host,
            "status": status,
            "maturity": self.maturity,
            "purpose": self.purpose,
            "replacement_ready": self.replacement_ready,
            "risks": list(self.risks),
            "recommended_next_step": self.recommended_next_step,
            "details": details or {},
        }


def _providers() -> dict[str, RuntimeProvider]:
    return {
        "picoclaw": RuntimeProvider(
            name="picoclaw",
            role="production_mcp_bridge",
            enabled=settings.PICOCLAW_ENABLED,
            required=settings.PICOCLAW_REQUIRED,
            host=settings.PICOCLAW_HOST,
            maturity="production",
            purpose="Governed local MCP gateway for IRIS agents.",
            replacement_ready=True,
            risks=("limited native evolutionary memory",),
            recommended_next_step="Keep as active runtime while memory/provider adapters are evaluated.",
        ),
        "hermes": RuntimeProvider(
            name="hermes",
            role="experimental_agent_runtime",
            enabled=settings.HERMES_ENABLED,
            required=settings.HERMES_REQUIRED,
            host=settings.HERMES_HOST,
            maturity="experimental",
            purpose="Self-improving agent runtime with persistent memory, skills and subagents.",
            replacement_ready=False,
            risks=(
                "native Windows support is not the safest production path",
                "requires WSL2/sandbox pilot before production replacement",
                "memory/skill writes need IRIS governance before enablement",
            ),
            recommended_next_step="Run Hermes behind WSL2 or container and connect it through this gateway as a pilot provider.",
        ),
        "memos": RuntimeProvider(
            name="memos",
            role="experimental_memory_os",
            enabled=settings.MEMOS_ENABLED,
            required=settings.MEMOS_REQUIRED,
            host=settings.MEMOS_HOST,
            maturity="experimental",
            purpose="Persistent multi-agent memory and skill evolution candidate.",
            replacement_ready=False,
            risks=(
                "must enforce no-secret memory policy",
                "requires retrieval quality and deletion feedback tests",
            ),
            recommended_next_step="Evaluate as memory layer before enabling autonomous skill evolution.",
        ),
    }


async def get_runtime_gateway_status() -> dict[str, Any]:
    providers = _providers()
    configured = settings.AGENT_RUNTIME_PROVIDER.strip().lower() or "picoclaw"
    active = providers.get(configured, providers["picoclaw"])

    provider_statuses = {
        "picoclaw": await _picoclaw_status(providers["picoclaw"]),
        "hermes": await _http_provider_status(providers["hermes"], cli_name="hermes"),
        "memos": await _http_provider_status(providers["memos"], cli_name=None),
    }

    active_status = provider_statuses.get(active.name, {})
    active_ready = active_status.get("status") == "online" and active.replacement_ready
    fallback_used = active.name != "picoclaw" and not active_ready

    return {
        "active_provider": "picoclaw" if fallback_used else active.name,
        "configured_provider": configured,
        "fallback_used": fallback_used,
        "production_safe": provider_statuses["picoclaw"].get("status") == "online",
        "decision": _decision(active, active_status, fallback_used),
        "providers": provider_statuses,
    }


async def _picoclaw_status(provider: RuntimeProvider) -> dict[str, Any]:
    if not provider.enabled:
        return provider.to_dict("disabled")
    health = await check_picoclaw_health()
    return provider.to_dict(str(health.get("status") or "unknown"), health)


async def _http_provider_status(provider: RuntimeProvider, *, cli_name: str | None) -> dict[str, Any]:
    if not provider.enabled:
        return provider.to_dict("disabled", _local_probe(cli_name))

    details = _local_probe(cli_name)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{provider.host.rstrip('/')}/health")
        details["health_http_status"] = response.status_code
        details["health_preview"] = response.text[:300]
        if response.status_code < 400:
            return provider.to_dict("online", details)
        return provider.to_dict("degraded", details)
    except Exception as exc:
        details["connection_error"] = str(exc)
        return provider.to_dict("offline", details)


def _local_probe(cli_name: str | None) -> dict[str, Any]:
    details: dict[str, Any] = {}
    if cli_name:
        details["cli_on_path"] = bool(shutil.which(cli_name))
    wsl = shutil.which("wsl")
    details["wsl_available"] = bool(wsl)
    if wsl:
        try:
            result = subprocess.run(
                ["wsl", "-l", "-q"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=5,
            )
            clean_stdout = result.stdout.replace("\x00", "")
            details["wsl_distros"] = [line.strip() for line in clean_stdout.splitlines() if line.strip()]
        except Exception as exc:
            details["wsl_probe_error"] = str(exc)
    return details


def _decision(active: RuntimeProvider, active_status: dict[str, Any], fallback_used: bool) -> str:
    if fallback_used:
        return (
            f"Configured provider '{active.name}' is not production-ready; IRIS is using PicoClaw fallback."
        )
    if active.name == "picoclaw":
        return "PicoClaw is the production MCP bridge. Hermes/MemOS remain evaluation providers."
    if active_status.get("status") == "online" and active.replacement_ready:
        return f"{active.name} is online and marked replacement-ready."
    return f"{active.name} is not approved for production replacement yet."
