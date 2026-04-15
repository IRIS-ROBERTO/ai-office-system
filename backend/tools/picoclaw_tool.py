"""
IRIS AI Office System — PicoClawMCPTool
Bridges IRIS agents to the PicoClaw MCP server for native integrations.

PicoClaw (by Sipeed) is an ultra-lightweight AI assistant in Go with
built-in MCP (Model Context Protocol) support. Running locally, it provides
a unified HTTP gateway to all connected MCP servers — giving IRIS agents
access to Gmail, Google Calendar, Notion, n8n, Supabase, GitHub, and any
other MCP you have configured, through a single consistent tool.

Architecture:
  IRIS Agent → PicoClawMCPTool → PicoClaw HTTP API (localhost:18790)
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
Config: see scripts/picoclaw_config.json for MCP server connections.

Requirements:
  PICOCLAW_HOST=http://localhost:18790 (default)
  PICOCLAW_ENABLED=true
  PICOCLAW_REQUIRED=false              (optional release dependency by default)
"""
import json
import logging
import os
import asyncio
import threading
import uuid
from pathlib import Path
from typing import Any, Type
from urllib.parse import urlparse, urlunparse

import httpx
import websockets
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.core.tool_governance import authorize_picoclaw_call

logger = logging.getLogger(__name__)


def _picoclaw_ws_url(host: str) -> str:
    parsed = urlparse(host)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, "/pico/ws", "", "", ""))


def _picoclaw_pico_token() -> str:
    configured = os.getenv("PICOCLAW_PICO_TOKEN", "iris-local-pico-token")
    if configured.startswith("pico-"):
        return configured

    pid_file = Path.home() / ".picoclaw" / ".picoclaw.pid"
    try:
        pid_data = json.loads(pid_file.read_text(encoding="utf-8"))
        runtime_token = str(pid_data.get("token") or "").strip()
        if runtime_token:
            return f"pico-{runtime_token}{configured}"
    except Exception:
        logger.debug("[PicoClawMCPTool] Could not read PicoClaw pid token", exc_info=True)

    return configured


def _run_async_blocking(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:  # pragma: no cover - defensive bridge for sync tools
            result["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


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
        host = getattr(settings, "PICOCLAW_HOST", "http://localhost:18790")

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
                return self._run_via_pico_channel(host, server, tool_name, arguments)

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

    def _run_via_pico_channel(
        self,
        host: str,
        server: str,
        tool_name: str,
        arguments: dict,
    ) -> str:
        token = _picoclaw_pico_token()
        timeout = float(os.getenv("PICOCLAW_WS_TIMEOUT_SECONDS", "90"))
        prompt = (
            "Execute this local MCP tool request through your registered tools. "
            "Do not invent tool output. If the tool is unavailable, say exactly which "
            "server/tool is missing.\n\n"
            f"server: {server}\n"
            f"tool: {tool_name}\n"
            f"arguments_json: {json.dumps(arguments, ensure_ascii=False)}\n\n"
            "Return a concise operational result."
        )
        try:
            result = _run_async_blocking(
                self._send_pico_message(
                    ws_url=_picoclaw_ws_url(host),
                    token=token,
                    prompt=prompt,
                    timeout=timeout,
                )
            )
            return f"PICOCLAW_OK_VIA_PICO {server}.{tool_name}\n{result}"
        except Exception as exc:
            logger.error("[PicoClawMCPTool] Pico channel error: %s", exc)
            return (
                "PICOCLAW_REST_UNSUPPORTED_AND_PICO_FAILED\n"
                "O release atual do PicoClaw nao expoe /mcp/call; a ponte tentou "
                f"usar /pico/ws e falhou: {exc}"
            )

    async def _send_pico_message(
        self,
        ws_url: str,
        token: str,
        prompt: str,
        timeout: float,
    ) -> str:
        session_id = f"iris-{uuid.uuid4().hex}"
        request_id = f"msg-{uuid.uuid4().hex}"
        headers = {"Authorization": f"Bearer {token}"}
        message = {
            "type": "message.send",
            "id": request_id,
            "session_id": session_id,
            "payload": {"content": prompt},
        }

        async with websockets.connect(
            f"{ws_url}?session_id={session_id}",
            additional_headers=headers,
            open_timeout=10,
            ping_interval=20,
        ) as websocket:
            await websocket.send(json.dumps(message, ensure_ascii=False))
            deadline = asyncio.get_running_loop().time() + timeout
            responses: list[str] = []
            while asyncio.get_running_loop().time() < deadline:
                remaining = max(1.0, deadline - asyncio.get_running_loop().time())
                raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                event = json.loads(raw)
                payload = event.get("payload") or {}
                if event.get("type") == "error":
                    raise RuntimeError(payload.get("message") or json.dumps(payload))
                if event.get("session_id") != session_id:
                    continue
                if event.get("type") != "message.create":
                    continue
                if payload.get("thought") is True:
                    continue
                content = str(payload.get("content") or "").strip()
                if content:
                    responses.append(content)
                    return "\n".join(responses)

        raise TimeoutError(f"Pico channel did not return a response within {timeout:.0f}s")


async def check_picoclaw_health() -> dict[str, Any]:
    enabled = getattr(settings, "PICOCLAW_ENABLED", True)
    host = getattr(settings, "PICOCLAW_HOST", "http://localhost:18790")
    required = getattr(settings, "PICOCLAW_REQUIRED", False)
    binary_path = Path(os.getenv("LOCALAPPDATA", "")) / "PicoClaw" / "picoclaw.exe"
    config_path = Path.home() / ".picoclaw" / "config.json"
    binary_size = binary_path.stat().st_size if binary_path.exists() else None
    binary_warning = (
        "Installed binary is too small for the PicoClaw CLI; reinstall with scripts/install_picoclaw.ps1."
        if binary_size is not None and binary_size < 10_000_000
        else None
    )
    if not enabled:
        return {
            "status": "disabled",
            "host": host,
            "required": required,
            "installed": binary_path.exists(),
            "binary_path": str(binary_path),
            "binary_size": binary_size,
            "binary_warning": binary_warning,
            "config_path": str(config_path),
        }

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{host}/health")
        if response.status_code >= 400:
            return {
                "status": "degraded",
                "host": host,
                "required": required,
                "installed": binary_path.exists(),
                "binary_path": str(binary_path),
                "binary_size": binary_size,
                "binary_warning": binary_warning,
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
            "required": required,
            "installed": binary_path.exists(),
            "binary_path": str(binary_path),
            "binary_size": binary_size,
            "binary_warning": binary_warning,
            "config_path": str(config_path),
            "health": body,
        }
    except httpx.ConnectError:
        return {
            "status": "offline",
            "host": host,
            "required": required,
            "installed": binary_path.exists(),
            "binary_path": str(binary_path),
            "binary_size": binary_size,
            "binary_warning": binary_warning,
            "config_path": str(config_path),
            "reason": binary_warning or "HTTP bridge is not accepting connections.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "host": host,
            "required": required,
            "installed": binary_path.exists(),
            "binary_path": str(binary_path),
            "binary_size": binary_size,
            "binary_warning": binary_warning,
            "config_path": str(config_path),
            "error": str(exc),
        }


def get_picoclaw_status() -> dict[str, Any]:
    return {
        "enabled": getattr(settings, "PICOCLAW_ENABLED", True),
        "host": getattr(settings, "PICOCLAW_HOST", "http://localhost:18790"),
        "required": getattr(settings, "PICOCLAW_REQUIRED", False),
        "binary_path": str(Path(os.getenv("LOCALAPPDATA", "")) / "PicoClaw" / "picoclaw.exe"),
        "binary_min_size_bytes": 10_000_000,
        "config_path": str(Path.home() / ".picoclaw" / "config.json"),
        "gateway": "PicoClaw MCP HTTP bridge",
        "control_model": "role_policy_plus_orchestrator_high_risk",
    }


def get_picoclaw_mcp_tool(agent_role: str, agent_id: str) -> PicoClawMCPTool:
    return PicoClawMCPTool(agent_role=agent_role, agent_id=agent_id)


# Ready-to-inject instance
picoclaw_mcp_tool = PicoClawMCPTool()
