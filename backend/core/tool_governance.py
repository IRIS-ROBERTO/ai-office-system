"""
Central governance for agent tools and PicoClaw MCP access.

Agents may receive operational powers, but the orchestrator owns high-risk
actions. This module keeps that contract explicit and inspectable by the API.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


READ_PREFIXES = (
    "get",
    "list",
    "read",
    "search",
    "fetch",
    "find",
    "query",
    "inspect",
)

WRITE_PREFIXES = (
    "create",
    "update",
    "delete",
    "write",
    "send",
    "trigger",
    "run",
    "execute",
    "commit",
    "push",
    "merge",
    "close",
    "archive",
)


@dataclass(frozen=True)
class ServerPolicy:
    server: str
    risk: str
    purpose: str
    allowed_roles: tuple[str, ...]
    write_roles: tuple[str, ...] = ("orchestrator",)

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": self.server,
            "risk": self.risk,
            "purpose": self.purpose,
            "allowed_roles": list(self.allowed_roles),
            "write_roles": list(self.write_roles),
        }


PICOCLAW_POLICIES: dict[str, ServerPolicy] = {
    "filesystem": ServerPolicy(
        server="filesystem",
        risk="controlled",
        purpose="Leitura e escrita local limitada ao workspace configurado no PicoClaw.",
        allowed_roles=(
            "orchestrator",
            "planner",
            "frontend",
            "backend",
            "qa",
            "security",
            "docs",
        ),
        write_roles=("orchestrator", "frontend", "backend", "docs"),
    ),
    "memory": ServerPolicy(
        server="memory",
        risk="safe",
        purpose="Memoria operacional local para aprendizados e contexto entre execucoes.",
        allowed_roles=(
            "orchestrator",
            "planner",
            "frontend",
            "backend",
            "qa",
            "security",
            "docs",
            "research",
            "strategy",
            "content",
            "seo",
            "social",
            "analytics",
        ),
        write_roles=(
            "orchestrator",
            "planner",
            "frontend",
            "backend",
            "qa",
            "security",
            "docs",
            "research",
            "strategy",
            "content",
            "seo",
            "social",
            "analytics",
        ),
    ),
    "sequential-thinking": ServerPolicy(
        server="sequential-thinking",
        risk="safe",
        purpose="Decomposicao estruturada de problemas antes da execucao.",
        allowed_roles=(
            "orchestrator",
            "planner",
            "qa",
            "security",
            "research",
            "strategy",
            "analytics",
        ),
        write_roles=(
            "orchestrator",
            "planner",
            "qa",
            "security",
            "research",
            "strategy",
            "analytics",
        ),
    ),
    "brave-search": ServerPolicy(
        server="brave-search",
        risk="safe",
        purpose="Pesquisa externa com fonte rastreavel.",
        allowed_roles=("orchestrator", "planner", "research", "strategy", "seo", "content"),
        write_roles=(),
    ),
    "github": ServerPolicy(
        server="github",
        risk="high",
        purpose="Operacoes remotas de repositorio. Escrita remota fica sob controle do orquestrador.",
        allowed_roles=(
            "orchestrator",
            "planner",
            "frontend",
            "backend",
            "qa",
            "security",
            "docs",
        ),
        write_roles=("orchestrator",),
    ),
    "notion": ServerPolicy(
        server="notion",
        risk="controlled",
        purpose="Registro de documentacao, decisoes e handoff operacional.",
        allowed_roles=("orchestrator", "docs", "strategy", "content"),
        write_roles=("orchestrator", "docs"),
    ),
    "n8n": ServerPolicy(
        server="n8n",
        risk="high",
        purpose="Automacoes externas. Disparo de workflow fica sob controle do orquestrador.",
        allowed_roles=("orchestrator", "social", "content"),
        write_roles=("orchestrator",),
    ),
    "supabase": ServerPolicy(
        server="supabase",
        risk="controlled",
        purpose="Consulta de dados operacionais e analytics.",
        allowed_roles=("orchestrator", "backend", "research", "strategy", "analytics"),
        write_roles=("orchestrator", "backend"),
    ),
}


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower().replace("_", "-")


def _is_write_tool(tool_name: str) -> bool:
    normalized = _normalize(tool_name)
    return any(normalized.startswith(prefix) for prefix in WRITE_PREFIXES)


def _is_read_tool(tool_name: str) -> bool:
    normalized = _normalize(tool_name)
    return any(normalized.startswith(prefix) for prefix in READ_PREFIXES)


def authorize_picoclaw_call(
    *,
    agent_role: str,
    server: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    role = _normalize(agent_role) or "unknown"
    server_key = _normalize(server)
    tool_key = _normalize(tool_name)
    policy = PICOCLAW_POLICIES.get(server_key)

    if policy is None:
        return {
            "allowed": False,
            "risk": "unknown",
            "reason": f"Servidor MCP '{server}' nao esta registrado na governanca.",
        }

    if role not in policy.allowed_roles:
        return {
            "allowed": False,
            "risk": policy.risk,
            "reason": f"Role '{agent_role}' nao tem permissao para usar '{server}'.",
        }

    is_write = _is_write_tool(tool_key)
    if is_write and role not in policy.write_roles:
        return {
            "allowed": False,
            "risk": policy.risk,
            "reason": (
                f"Tool '{tool_name}' parece causar efeito externo. "
                "Apenas o orquestrador ou papeis explicitamente liberados podem executar escrita."
            ),
        }

    return {
        "allowed": True,
        "risk": policy.risk,
        "mode": "write" if is_write else "read" if _is_read_tool(tool_key) else "unknown",
        "reason": "Autorizado pela politica de capacidades do papel.",
        "server": server_key,
        "tool": tool_key,
        "agent_role": role,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "argument_keys": sorted((arguments or {}).keys()),
    }


def get_role_tool_policy(role: str) -> dict[str, Any]:
    role_key = _normalize(role)
    servers = []
    for policy in PICOCLAW_POLICIES.values():
        if role_key in policy.allowed_roles:
            item = policy.to_dict()
            item["can_write"] = role_key in policy.write_roles
            servers.append(item)
    return {
        "role": role_key,
        "picoclaw_servers": servers,
        "rules": [
            "Agentes podem usar apenas servidores MCP liberados para seu papel.",
            "Operacoes externas de alto risco ficam concentradas no orquestrador.",
            "Commits locais devem continuar usando github_commit_tool com evidencia.",
            "Toda chamada PicoClaw deve registrar servidor, tool e chaves dos argumentos.",
        ],
    }


def list_tool_policies() -> dict[str, Any]:
    return {
        "picoclaw": [policy.to_dict() for policy in PICOCLAW_POLICIES.values()],
        "read_prefixes": list(READ_PREFIXES),
        "write_prefixes": list(WRITE_PREFIXES),
    }
