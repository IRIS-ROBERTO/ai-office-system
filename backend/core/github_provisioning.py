"""
Non-destructive GitHub provisioning diagnostics for IRIS delivery automation.
"""
from __future__ import annotations

import subprocess
from typing import Any

import httpx

from backend.config.settings import settings


GITHUB_API = "https://api.github.com"


def get_github_provisioning_status() -> dict[str, Any]:
    owner = settings.GITHUB_DEFAULT_ORG or settings.GITHUB_USERNAME
    status: dict[str, Any] = {
        "configured": bool(settings.GITHUB_TOKEN),
        "owner": owner,
        "default_org": settings.GITHUB_DEFAULT_ORG or "",
        "configured_username": settings.GITHUB_USERNAME,
        "authenticated": False,
        "login": "",
        "scopes": [],
        "rate_limit": {},
        "main_repo": {
            "name": "ai-office-system",
            "accessible": False,
            "push_permission": False,
            "admin_permission": False,
            "status_code": None,
        },
        "gh_cli": _gh_cli_status(),
        "standalone_repo_creation_ready": False,
        "principal_repo_push_ready": False,
        "blockers": [],
        "warnings": [],
        "next_actions": [],
    }

    if not settings.GITHUB_TOKEN:
        _add_blocker(status, "github_token_missing", "GITHUB_TOKEN nao configurado; repos standalone nao podem ser criados ou publicados.")
        _finalize(status)
        return status

    headers = {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        with httpx.Client(headers=headers, timeout=20) as client:
            user_response = client.get(f"{GITHUB_API}/user")
            _capture_headers(status, user_response)
            if user_response.status_code != 200:
                status["auth_status_code"] = user_response.status_code
                _add_blocker(status, "github_auth_failed", f"GitHub rejeitou o token com HTTP {user_response.status_code}.")
                _finalize(status)
                return status

            login = str(user_response.json().get("login") or "")
            status["authenticated"] = True
            status["login"] = login

            if not owner:
                _add_blocker(status, "github_owner_missing", "GITHUB_USERNAME ou GITHUB_DEFAULT_ORG precisa estar configurado.")
            elif not settings.GITHUB_DEFAULT_ORG and login and owner.lower() != login.lower():
                _add_warning(
                    status,
                    "github_owner_mismatch",
                    f"Owner configurado '{owner}' difere do usuario autenticado '{login}'. Use GITHUB_DEFAULT_ORG para organizacao.",
                )

            if owner:
                repo_response = client.get(f"{GITHUB_API}/repos/{owner}/ai-office-system")
                status["main_repo"]["status_code"] = repo_response.status_code
                if repo_response.status_code == 200:
                    permissions = repo_response.json().get("permissions") or {}
                    status["main_repo"]["accessible"] = True
                    status["main_repo"]["push_permission"] = bool(permissions.get("push"))
                    status["main_repo"]["admin_permission"] = bool(permissions.get("admin"))
                else:
                    _add_warning(
                        status,
                        "main_repo_not_accessible",
                        f"Repositorio {owner}/ai-office-system nao acessivel via token: HTTP {repo_response.status_code}.",
                    )
    except Exception as exc:
        _add_blocker(status, "github_probe_failed", f"Falha ao consultar GitHub: {type(exc).__name__}.")
        status["probe_error"] = str(exc)[:240]
        _finalize(status)
        return status

    scopes = set(status.get("scopes") or [])
    has_classic_repo_scope = bool({"repo", "public_repo"} & scopes)
    fine_grained_or_app_token = status["authenticated"] and not scopes

    if not has_classic_repo_scope and fine_grained_or_app_token:
        _add_warning(
            status,
            "github_fine_grained_scope_unknown",
            "Token autenticou, mas GitHub nao expos scopes classicos; confirme Contents:write e Administration:write nos repos necessarios.",
        )
    elif not has_classic_repo_scope:
        _add_blocker(
            status,
            "github_repo_scope_missing",
            "Token nao informa escopo repo/public_repo; criacao e push de repos standalone podem falhar.",
        )

    if status["main_repo"]["accessible"] and not status["main_repo"]["push_permission"]:
        _add_blocker(
            status,
            "main_repo_push_permission_missing",
            "Token acessa o repo principal, mas nao possui permissao de push nele.",
        )

    blocking_codes = {item["code"] for item in status["blockers"]}
    status["standalone_repo_creation_ready"] = (
        status["authenticated"]
        and bool(owner)
        and not blocking_codes.intersection({"github_token_missing", "github_auth_failed", "github_owner_missing", "github_repo_scope_missing"})
    ) or bool(status.get("gh_cli", {}).get("authenticated") and owner)
    status["principal_repo_push_ready"] = bool(status["main_repo"]["push_permission"])
    _finalize(status)
    return status


def _gh_cli_status() -> dict[str, Any]:
    result = {
        "available": False,
        "authenticated": False,
        "account": "",
        "scopes": [],
    }
    try:
        version = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=10,
        )
        result["available"] = version.returncode == 0
        if not result["available"]:
            return result

        auth = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
        )
        text = (auth.stdout or "") + "\n" + (auth.stderr or "")
        result["authenticated"] = auth.returncode == 0 or "Logged in to github.com account" in text
        for line in text.splitlines():
            if "Logged in to github.com account" in line:
                result["account"] = line.split("account", 1)[1].split("(", 1)[0].strip()
            if "Token scopes:" in line:
                scopes_text = line.split("Token scopes:", 1)[1].strip().strip("'")
                result["scopes"] = [scope.strip().strip("'") for scope in scopes_text.split(",") if scope.strip()]
        return result
    except Exception as exc:
        result["error"] = type(exc).__name__
        return result


def _capture_headers(status: dict[str, Any], response: httpx.Response) -> None:
    scopes = response.headers.get("x-oauth-scopes", "")
    status["scopes"] = sorted(scope.strip() for scope in scopes.split(",") if scope.strip())
    status["rate_limit"] = {
        "limit": response.headers.get("x-ratelimit-limit", ""),
        "remaining": response.headers.get("x-ratelimit-remaining", ""),
        "reset": response.headers.get("x-ratelimit-reset", ""),
    }


def _add_blocker(status: dict[str, Any], code: str, message: str) -> None:
    status["blockers"].append({"code": code, "message": message})


def _add_warning(status: dict[str, Any], code: str, message: str) -> None:
    status["warnings"].append({"code": code, "message": message})


def _finalize(status: dict[str, Any]) -> None:
    codes = {item["code"] for item in status["blockers"] + status["warnings"]}
    actions: list[str] = []
    if "github_token_missing" in codes:
        actions.append("Configurar GITHUB_TOKEN com permissao para criar repositorios e escrever contents.")
    if "github_auth_failed" in codes:
        actions.append("Gerar novo token GitHub e atualizar .env/local security store.")
    if "github_owner_mismatch" in codes:
        actions.append("Definir GITHUB_DEFAULT_ORG quando o owner alvo for organizacao diferente do usuario autenticado.")
    if "github_repo_scope_missing" in codes or "github_fine_grained_scope_unknown" in codes:
        actions.append("Validar escopos: classic PAT precisa repo/public_repo; fine-grained precisa Contents write e Administration write.")
    if "main_repo_push_permission_missing" in codes:
        actions.append("Conceder permissao de write no repo principal ou usar token de usuario/app com acesso ao repo.")
    if status.get("gh_cli", {}).get("authenticated") and "github_fine_grained_scope_unknown" in codes:
        actions.append("Fallback gh CLI disponivel para criacao/push de repos standalone quando o token da API for restrito.")
    if not actions and status.get("standalone_repo_creation_ready"):
        actions.append("Executar smoke standalone com criacao de repo dedicado e push confirmado.")
    status["next_actions"] = actions
