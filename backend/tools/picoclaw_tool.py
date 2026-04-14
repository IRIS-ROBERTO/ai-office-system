"""
IRIS AI Office System — PicoClawMCPTool
Bridges IRIS agents to the PicoClaw MCP server for native integrations.

PicoClaw (by Sipeed) is an ultra-lightweight AI assistant in Go with
built-in MCP (Model Context Protocol) support. Running locally, it provides
a unified HTTP gateway to all connected MCP servers — giving IRIS agents
access to Gmail, Google Calendar, Notion, n8n, Supabase, GitHub, and any
other MCP you have configured, through a single consistent tool.

Architecture:
  IRIS Agent → PicoClawMCPTool → PicoClaw HTTP API (localhost:8765)
                                       ↓ MCP protocol
                                  ┌────────────────────┐
                                  │ Gmail MCP          │
                                  │ Google Calendar MCP │
                                  │ Notion MCP         │
                                  │ n8n MCP            │
                                  │ Supabase MCP       │
                                  │ GitHub MCP         │
                                  └────────────────────┘

Setup: run scripts/install_picoclaw.ps1 to install PicoClaw locally.
Config: see scripts/picoclaw_config.yaml for MCP server connections.

Requirements:
  PICOCLAW_HOST=http://localhost:8765  (default)
  PICOCLAW_ENABLED=true
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.core.tool_governance import authorize_picoclaw_call

logger = logging.getLogger(__name__)


class PicoClawInput(BaseModel):
    server: str = Field(
        description=(
            "Nome do MCP server alvo. Exemplos: "
            "'gmail', 'gcal', 'notion', 'n8n', 'supabase', 'github', 'slack'"
        )
    )
    tool_name: str = Field(
        description="Nome da tool no MCP server (ex: 'gmail_send', 'gcal_create_event')"
    )
    arguments: dict = Field(
        default_factory=dict,
        description="Argumentos para a tool MCP como dict JSON",
    )


class PicoClawMCPTool(BaseTool):
    """
    Gateway unificado para todos os MCPs via PicoClaw.
    Permite que agentes acessem Gmail, Google Calendar, Notion, n8n, GitHub
    e qualquer MCP configurado, com uma única interface consistente.
    """

    name: str = "picoclaw_mcp"
    description: str = (
        "Acessa qualquer serviço externo via PicoClaw MCP bridge. "
        "Servidores disponíveis: gmail (ler/enviar emails), "
        "gcal (criar/listar eventos), "
        "notion (ler/escrever páginas), "
        "n8n (disparar workflows), "
        "supabase (consultar banco), "
        "github (criar repos/commits/PRs). "
        "Use: server='gmail', tool_name='gmail_send', arguments={'to':..., 'subject':..., 'body':...}"
    )
    args_schema: Type[BaseModel] = PicoClawInput
    agent_role: str = "orchestrator"
    agent_id: str = "orchestrator_senior_01"

    def _run(
        self,
        server: str,
        tool_name: str,
        arguments: dict,
    ) -> str:
        enabled = getattr(settings, "PICOCLAW_ENABLED", True)
        host = getattr(settings, "PICOCLAW_HOST", "http://localhost:8765")

        if not enabled:
            return "PICOCLAW_DISABLED: PICOCLAW_ENABLED=false."

        decision = authorize_picoclaw_call(
            agent_role=self.agent_role,
            server=server,
            tool_name=tool_name,
            arguments=arguments,
        )
        if not decision["allowed"]:
            logger.warning(
                "[PicoClawMCPTool] denied agent=%s role=%s server=%s tool=%s reason=%s",
                self.agent_id,
                self.agent_role,
                server,
                tool_name,
                decision["reason"],
            )
            return (
                "PICOCLAW_DENIED\n"
                f"agent_id: {self.agent_id}\n"
                f"agent_role: {self.agent_role}\n"
                f"server: {server}\n"
                f"tool: {tool_name}\n"
                f"reason: {decision['reason']}"
            )

        try:
            payload = {
                "server": server,
                "tool": tool_name,
                "arguments": arguments,
            }

            resp = httpx.post(
                f"{host}/mcp/call",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if resp.status_code == 404:
                return (
                    f"PICOCLAW_NOT_FOUND: tool '{tool_name}' no servidor '{server}'. "
                    f"Verifique se o MCP server está configurado em picoclaw_config.yaml."
                )

            resp.raise_for_status()
            result = resp.json()

            logger.info(
                "[PicoClawMCPTool] agent=%s role=%s %s.%s executado com sucesso.",
                self.agent_id,
                self.agent_role,
                server,
                tool_name,
            )
            return (
                f"PICOCLAW_OK {server}.{tool_name}\n"
                + json.dumps(result, ensure_ascii=False, indent=2)
            )

        except httpx.ConnectError:
            return (
                f"PICOCLAW_OFFLINE: PicoClaw nao acessivel em {host}. "
                "Execute scripts/install_picoclaw.ps1 e confirme que o HTTP bridge esta ouvindo."
            )
        except httpx.HTTPStatusError as exc:
            return f"PICOCLAW_HTTP_ERROR {exc.response.status_code}: {exc.response.text[:400]}"
        except Exception as exc:
            logger.error("[PicoClawMCPTool] Erro: %s", exc)
            return f"PICOCLAW_ERROR: {exc}"


async def check_picoclaw_health() -> dict[str, Any]:
    enabled = getattr(settings, "PICOCLAW_ENABLED", True)
    host = getattr(settings, "PICOCLAW_HOST", "http://localhost:8765")
    binary_path = Path(os.getenv("LOCALAPPDATA", "")) / "PicoClaw" / "picoclaw.exe"
    config_path = Path(os.getenv("LOCALAPPDATA", "")) / "PicoClaw" / "config.yaml"
    if not enabled:
        return {
            "status": "disabled",
            "host": host,
            "installed": binary_path.exists(),
            "binary_path": str(binary_path),
            "config_path": str(config_path),
        }

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{host}/health")
        if response.status_code >= 400:
            return {
                "status": "degraded",
                "host": host,
                "installed": binary_path.exists(),
                "binary_path": str(binary_path),
                "config_path": str(config_path),
                "http_status": response.status_code,
                "body": response.text[:300],
            }
        try:
            body: Any = response.json()
        except Exception:
            body = response.text[:300]
        return {
            "status": "online",
            "host": host,
            "installed": binary_path.exists(),
            "binary_path": str(binary_path),
            "config_path": str(config_path),
            "health": body,
        }
    except httpx.ConnectError:
        return {
            "status": "offline",
            "host": host,
            "installed": binary_path.exists(),
            "binary_path": str(binary_path),
            "config_path": str(config_path),
            "reason": "HTTP bridge is not accepting connections.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "host": host,
            "installed": binary_path.exists(),
            "binary_path": str(binary_path),
            "config_path": str(config_path),
            "error": str(exc),
        }


def get_picoclaw_status() -> dict[str, Any]:
    return {
        "enabled": getattr(settings, "PICOCLAW_ENABLED", True),
        "host": getattr(settings, "PICOCLAW_HOST", "http://localhost:8765"),
        "binary_path": str(Path(os.getenv("LOCALAPPDATA", "")) / "PicoClaw" / "picoclaw.exe"),
        "config_path": str(Path(os.getenv("LOCALAPPDATA", "")) / "PicoClaw" / "config.yaml"),
        "gateway": "PicoClaw MCP HTTP bridge",
        "control_model": "role_policy_plus_orchestrator_high_risk",
    }


def get_picoclaw_mcp_tool(agent_role: str, agent_id: str) -> PicoClawMCPTool:
    return PicoClawMCPTool(agent_role=agent_role, agent_id=agent_id)


# Ready-to-inject instance
picoclaw_mcp_tool = PicoClawMCPTool()
