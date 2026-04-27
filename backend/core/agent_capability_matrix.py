"""
Inspectable capability matrix for IRIS agents.

This module is intentionally static and explicit: production operators need to
know what every specialist is allowed to do before a task starts.
"""
from __future__ import annotations

from typing import Any

from backend.core.capability_access import get_agent_access_profile
from backend.core.runtime_registry import agent_registry, seed_agent_registry
from backend.core.tool_governance import get_role_tool_policy
from backend.tools.brain_router import get_brain_status
from backend.tools.picoclaw_tool import get_picoclaw_status


ROLE_CAPABILITIES: dict[str, dict[str, Any]] = {
    "orchestrator": {
        "autonomy": "executive_control",
        "declared_tools": ["task_router", "quality_gate", "delivery_runner", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "owns planning, routing, approval and high-risk external writes",
        "upgrade_track": ["runtime provider adapter", "long-horizon planning", "cross-agent memory arbitration"],
    },
    "planner": {
        "autonomy": "bounded_specialist",
        "declared_tools": ["workspace_file", "github_commit", "web_search", "file_read", "directory_read", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "architecture, task breakdown, acceptance criteria and handoffs",
        "upgrade_track": ["spec-driven development kit", "architecture decision memory"],
    },
    "frontend": {
        "autonomy": "bounded_specialist",
        "declared_tools": ["workspace_file", "github_commit", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "UI, accessibility, performance and frontend build integrity",
        "upgrade_track": ["browser automation", "visual regression", "component library MCP"],
    },
    "backend": {
        "autonomy": "bounded_specialist",
        "declared_tools": ["workspace_file", "github_commit", "web_search", "file_read", "code_executor", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "APIs, data contracts, local automation and backend validation",
        "upgrade_track": ["sandboxed execution", "schema migration planner", "service contract testing"],
    },
    "qa": {
        "autonomy": "bounded_specialist",
        "declared_tools": ["workspace_file", "github_commit", "file_read", "directory_read", "code_executor", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "test strategy, smoke checks, regression and release evidence",
        "upgrade_track": ["Playwright/browser-use bridge", "coverage trend memory", "failure clustering"],
    },
    "security": {
        "autonomy": "controlled_specialist",
        "declared_tools": ["workspace_file", "github_commit", "file_read", "web_search", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed_no_secret_storage",
        "segmentation": "threat modeling, OWASP review, secret hygiene and hardening",
        "upgrade_track": ["SAST scanners", "dependency audit", "policy-as-code gate"],
    },
    "docs": {
        "autonomy": "bounded_specialist",
        "declared_tools": ["workspace_file", "github_commit", "file_read", "web_search", "notion_write", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "README, runbooks, API docs, decisions and handoff",
        "upgrade_track": ["knowledge graph", "docs freshness checks"],
    },
    "research": {
        "autonomy": "bounded_specialist",
        "declared_tools": ["github_commit", "web_search", "scrape_website", "supabase_query", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "market, competitor and external technical research",
        "upgrade_track": ["source ranking", "freshness scoring", "research memory"],
    },
    "strategy": {
        "autonomy": "bounded_specialist",
        "declared_tools": ["github_commit", "web_search", "notion_write", "supabase_query", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "roadmap, positioning, metrics and executive decisions",
        "upgrade_track": ["scenario planning", "portfolio memory"],
    },
    "content": {
        "autonomy": "bounded_specialist",
        "declared_tools": ["github_commit", "web_search", "notion_write", "n8n_workflow", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "copy, narrative, campaigns and creative iteration",
        "upgrade_track": ["brand memory", "content performance feedback"],
    },
    "seo": {
        "autonomy": "bounded_specialist",
        "declared_tools": ["github_commit", "web_search", "scrape_website", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "technical SEO, semantic planning and search optimization",
        "upgrade_track": ["SERP tracking", "schema validation"],
    },
    "social": {
        "autonomy": "controlled_specialist",
        "declared_tools": ["github_commit", "n8n_workflow", "notion_write", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "social calendar, distribution and workflow activation",
        "upgrade_track": ["approval queue", "channel performance loop"],
    },
    "analytics": {
        "autonomy": "bounded_specialist",
        "declared_tools": ["github_commit", "supabase_query", "web_search", "picoclaw_mcp"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "metrics, bottlenecks, dashboards and impact analysis",
        "upgrade_track": ["anomaly detection", "delivery intelligence"],
    },
    "scout": {
        "autonomy": "autonomous_scheduler",
        "declared_tools": ["github_search", "huggingface_search", "web_search", "research_store"],
        "memory_posture": "shared_memory_allowed",
        "segmentation": "GitHub trending, HuggingFace models/datasets, project scoring and combination analysis",
        "upgrade_track": ["arxiv integration", "patent search", "competitor tracking", "market signal alerts"],
    },
}


def build_agent_capability(agent_id: str) -> dict[str, Any]:
    seed_agent_registry()
    agent = agent_registry.get(agent_id)
    if not agent:
        raise KeyError(agent_id)
    role = str(agent["agent_role"])
    profile = ROLE_CAPABILITIES.get(role, {})
    brain_profiles = (get_brain_status().get("profiles") or {})
    return {
        "agent_id": agent_id,
        "role": role,
        "team": str(agent["team"]),
        "autonomy": profile.get("autonomy", "unknown"),
        "segmentation": profile.get("segmentation", ""),
        "declared_tools": profile.get("declared_tools", []),
        "memory_posture": profile.get("memory_posture", "unknown"),
        "tool_policy": get_role_tool_policy(role),
        "brain_profile": brain_profiles.get(role, {}),
        "picoclaw": get_picoclaw_status(),
        "access_policy": get_agent_access_profile(agent_id, agent_role=role),
        "upgrade_track": profile.get("upgrade_track", []),
    }


def build_agent_capability_matrix() -> dict[str, Any]:
    seed_agent_registry()
    items = [build_agent_capability(agent_id) for agent_id in sorted(agent_registry)]
    total = len(items)
    mcp_enabled = sum(1 for item in items if item.get("tool_policy", {}).get("picoclaw_servers"))
    return {
        "total_agents": total,
        "mcp_policy_coverage": f"{mcp_enabled}/{total}",
        "memory_strategy": "PicoClaw memory MCP now covers every canonical role by policy; CrewAI memory remains disabled to avoid uncontrolled context bloat.",
        "runtime_recommendation": "Keep PicoClaw as production MCP bridge; evaluate Hermes Agent and MemOS through /integrations/runtime-gateway before replacement.",
        "items": items,
    }
