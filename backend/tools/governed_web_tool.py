"""
Governed Web access tools for IRIS agents.

All Web actions must pass through Capability Access before touching a URL.
This module starts with deterministic HTTP read access and exposes a browser
preflight contract that browser-use/Playwright adapters can reuse.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from backend.core.capability_access import authorize_capability_use


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_SCRIPT_RE = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_TAGS_RE = re.compile(r"<[^>]+>")
_MAX_BODY_CHARS = 5000
_ALLOWED_READ_METHODS = {"GET", "HEAD"}


def governed_web_fetch(
    *,
    agent_id: str,
    task_id: str,
    url: str,
    method: str = "GET",
    timeout_seconds: float = 10.0,
    tool_name: str = "governed_web_fetch",
) -> dict[str, Any]:
    method_key = method.strip().upper() or "GET"
    if method_key not in _ALLOWED_READ_METHODS:
        return {
            "allowed": False,
            "status": "blocked",
            "reason": f"HTTP method {method_key} is not a governed read method.",
        }

    authz = authorize_capability_use(
        agent_id=agent_id,
        task_id=task_id,
        resource_type="web",
        resource=url,
        access_level="read",
        tool_name=tool_name,
    )
    if not authz["allowed"]:
        return {
            "allowed": False,
            "status": "blocked",
            "authorization": authz,
            "reason": authz["reason"],
        }

    normalized_url = authz["normalized_resource"]
    try:
        with httpx.Client(
            timeout=max(1.0, min(float(timeout_seconds or 10.0), 30.0)),
            follow_redirects=True,
            headers={"User-Agent": "IRIS-Governed-Web/1.0"},
        ) as client:
            response = client.request(method_key, normalized_url)
    except httpx.HTTPError as exc:
        return {
            "allowed": True,
            "status": "failed",
            "authorization": authz,
            "url": normalized_url,
            "reason": f"HTTP request failed: {exc}",
        }

    body = response.text if method_key != "HEAD" else ""
    return {
        "allowed": True,
        "status": "fetched",
        "authorization": authz,
        "url": str(response.url),
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "title": _extract_title(body),
        "text_preview": _text_preview(body),
        "body_truncated": len(body) > _MAX_BODY_CHARS,
    }


def governed_browser_preflight(
    *,
    agent_id: str,
    task_id: str,
    url: str,
    action: str,
    tool_name: str = "browser-use",
) -> dict[str, Any]:
    action_key = action.strip().lower()
    access_level = "read" if action_key in {"open", "screenshot", "inspect"} else "control"
    authz = authorize_capability_use(
        agent_id=agent_id,
        task_id=task_id,
        resource_type="web",
        resource=url,
        access_level=access_level,
        tool_name=tool_name,
    )
    return {
        "allowed": authz["allowed"],
        "status": "authorized" if authz["allowed"] else "blocked",
        "action": action_key,
        "required_access_level": access_level,
        "authorization": authz,
        "adapter_contract": {
            "before_action": "Call this preflight immediately before browser-use/Playwright action.",
            "on_blocked": "Do not execute the browser action; request a stronger grant.",
            "on_allowed": "Execute only the declared action against the authorized URL scope.",
        },
    }


def _extract_title(body: str) -> str:
    if not body:
        return ""
    match = _TITLE_RE.search(body)
    if not match:
        return ""
    return _compact_text(match.group(1))[:200]


def _text_preview(body: str) -> str:
    if not body:
        return ""
    text = _SCRIPT_RE.sub(" ", body)
    text = _STYLE_RE.sub(" ", text)
    text = _TAGS_RE.sub(" ", text)
    return _compact_text(text)[:_MAX_BODY_CHARS]


def _compact_text(value: str) -> str:
    return " ".join((value or "").split())
