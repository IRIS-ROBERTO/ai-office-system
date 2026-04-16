"""
AI Office System — GitHub / Git Tool
Ferramenta central para versionar entregáveis dos agentes.

Modo preferencial:
- opera no repositório local com git add/commit/push

Modo legado:
- escreve um único arquivo via GitHub Contents API
"""
import base64
import logging
import subprocess
from pathlib import Path
from urllib.parse import quote
from typing import Optional

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.core.gold_standard import GENERATED_PROJECTS_ROOT, REPO_ROOT

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
BLOCKED_COMMIT_PARTS = {".git", ".runtime", ".venv", "_system", "node_modules", "dist", "__pycache__"}
BLOCKED_COMMIT_FILES = {".env", ".env.local"}


class GitHubCommitInput(BaseModel):
    repo_name: Optional[str] = Field(default=None, description="Nome do repositório remoto no GitHub")
    file_path: Optional[str] = Field(default=None, description="Arquivo remoto no modo legado da API GitHub")
    content: Optional[str] = Field(default=None, description="Conteúdo completo do arquivo no modo legado")
    commit_message: str = Field(description="Mensagem de commit descritiva")
    branch: str = Field(default="main", description="Branch alvo")
    create_repo_if_missing: bool = Field(default=True)
    repo_path: str = Field(
        default=".",
        description="Caminho do repositório local. Use '.' para o workspace atual.",
    )
    file_paths: list[str] = Field(
        default_factory=list,
        description="Arquivos locais para staging e commit. Ex.: ['frontend/src/App.tsx']",
    )
    push: bool = Field(default=False, description="Se true, faz push após o commit local")
    init_repo_if_missing: bool = Field(default=True, description="Inicializa git init quando repo_path ainda não é repositório")


class GitHubTool(BaseTool):
    """
    Faz commit de entregáveis dos agentes.

    Preferência absoluta: operar no repositório local com file_paths.
    """

    name: str = "github_commit"
    description: str = (
        "Versiona mudanças reais. Use com repo_path + file_paths + commit_message "
        "para executar git add e git commit no repositório local. "
        "Antes de usar, altere arquivos reais com workspace_file e valide com diff/status. "
        "Compatibilidade: também aceita repo_name + file_path + content para escrever um "
        "único arquivo via API do GitHub."
    )
    args_schema: type[BaseModel] = GitHubCommitInput

    def _run(
        self,
        repo_name: Optional[str] = None,
        file_path: Optional[str] = None,
        content: Optional[str] = None,
        commit_message: str = "",
        branch: str = "main",
        create_repo_if_missing: bool = True,
        repo_path: str = ".",
        file_paths: Optional[list[str]] = None,
        push: bool = False,
        init_repo_if_missing: bool = True,
    ) -> str:
        local_paths = file_paths or []
        if local_paths:
            return self._local_commit(
                repo_path=repo_path,
                file_paths=local_paths,
                commit_message=commit_message,
                branch=branch,
                push=push,
                init_repo_if_missing=init_repo_if_missing,
            )

        if repo_name and file_path and content is not None:
            import asyncio

            return asyncio.run(
                self._remote_commit(
                    repo_name=repo_name,
                    file_path=file_path,
                    content=content,
                    commit_message=commit_message,
                    branch=branch,
                    create_repo_if_missing=create_repo_if_missing,
                )
            )

        return (
            "ERROR: Parametros insuficientes para github_commit. "
            "Modo recomendado: informe file_paths + commit_message. "
            "Modo legado: repo_name + file_path + content + commit_message."
        )

    def _local_commit(
        self,
        repo_path: str,
        file_paths: list[str],
        commit_message: str,
        branch: str,
        push: bool,
        init_repo_if_missing: bool,
    ) -> str:
        try:
            repo_root = self._resolve_repo_root(repo_path, init_repo_if_missing=init_repo_if_missing)
        except RuntimeError as exc:
            return f"ERROR: {exc}"

        if not commit_message.strip():
            return "ERROR: commit_message esta vazio. Informe uma mensagem objetiva do entregavel."

        try:
            normalized_paths = [self._normalize_commit_path(repo_root, item) for item in file_paths if item]
        except RuntimeError as exc:
            return f"ERROR: {exc}"

        if not normalized_paths:
            return "ERROR: file_paths esta vazio. Informe os arquivos que devem entrar no commit."

        status_before = self._git(repo_root, ["status", "--short", "--"] + normalized_paths, check=False)
        if not status_before.stdout.strip():
            return (
                "WARN: Nenhuma alteracao detectada nos caminhos informados. "
                f"Arquivos observados: {', '.join(normalized_paths)}"
            )

        add_result = self._git(repo_root, ["add", "--"] + normalized_paths, check=False)
        if add_result.returncode != 0:
            message = (add_result.stderr or add_result.stdout or "").strip()
            return f"ERROR: git add falhou: {message}"

        staged = self._git(repo_root, ["diff", "--cached", "--name-only", "--"] + normalized_paths, check=False)
        staged_files = [line.strip() for line in staged.stdout.splitlines() if line.strip()]
        if not staged_files:
            return "WARN: Nenhum arquivo foi stageado para commit."

        commit_result = self._git(repo_root, ["commit", "-m", commit_message], check=False)
        if commit_result.returncode != 0:
            message = (commit_result.stderr or commit_result.stdout or "").strip()
            return f"ERROR: git commit falhou: {message}"

        commit_sha = self._git(repo_root, ["rev-parse", "--short", "HEAD"]).stdout.strip()
        current_branch = self._git(repo_root, ["branch", "--show-current"], check=False).stdout.strip() or branch

        push_summary = "push desabilitado"
        if push:
            push_result = self._push(repo_root, current_branch)
            if push_result.returncode != 0:
                message = (push_result.stderr or push_result.stdout or "").strip()
                return (
                    f"WARN: Commit local criado ({commit_sha}), mas o push falhou: {message}"
                )
            push_summary = f"push feito para origin/{current_branch}"

        logger.info(
            "[GitHubTool] Commit local criado em %s: %s (%s)",
            repo_root,
            commit_sha,
            ", ".join(staged_files),
        )
        return (
            f"OK: Commit local realizado em {repo_root}\n"
            f"SHA: {commit_sha}\n"
            f"Branch: {current_branch}\n"
            f"Arquivos: {', '.join(staged_files)}\n"
            f"Status: {push_summary}"
        )

    def _push(self, repo_root: Path, current_branch: str) -> subprocess.CompletedProcess[str]:
        remote = self._git(repo_root, ["remote", "get-url", "origin"], check=False)
        remote_url = (remote.stdout or "").strip()
        if remote.returncode == 0 and settings.GITHUB_TOKEN and "github.com" in remote_url:
            push_url = self._remote_url_with_token(remote_url, settings.GITHUB_TOKEN)
            return self._git(repo_root, ["push", push_url, f"HEAD:{current_branch}"], check=False)
        return self._git(repo_root, ["push", "origin", current_branch], check=False)

    def _remote_url_with_token(self, remote_url: str, token: str) -> str:
        safe_token = quote(token, safe="")
        if remote_url.startswith("https://github.com/"):
            return remote_url.replace("https://github.com/", f"https://x-access-token:{safe_token}@github.com/", 1)
        if remote_url.startswith("https://"):
            return remote_url.replace("https://", f"https://x-access-token:{safe_token}@", 1)
        if remote_url.startswith("git@github.com:"):
            path = remote_url.removeprefix("git@github.com:")
            return f"https://x-access-token:{safe_token}@github.com/{path}"
        return remote_url

    async def _remote_commit(
        self,
        repo_name: str,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str,
        create_repo_if_missing: bool,
    ) -> str:
        headers = {
            "Authorization": f"token {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        owner = settings.GITHUB_DEFAULT_ORG or settings.GITHUB_USERNAME

        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            repo_exists = await self._check_repo(client, owner, repo_name)

            if not repo_exists and create_repo_if_missing:
                await self._create_repo(client, repo_name)
                logger.info("Repositório '%s' criado no GitHub", repo_name)

            sha = await self._get_file_sha(client, owner, repo_name, file_path, branch)
            encoded = base64.b64encode(content.encode()).decode()
            payload = {
                "message": commit_message,
                "content": encoded,
                "branch": branch,
            }
            if sha:
                payload["sha"] = sha

            url = f"{GITHUB_API}/repos/{owner}/{repo_name}/contents/{file_path}"
            resp = await client.put(url, json=payload)
            resp.raise_for_status()

            commit_url = resp.json()["commit"]["html_url"]
            logger.info("Commit remoto realizado: %s", commit_url)
        return f"OK: Commit remoto realizado: {commit_url}"

    async def _check_repo(self, client: httpx.AsyncClient, owner: str, repo: str) -> bool:
        resp = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}")
        return resp.status_code == 200

    async def _create_repo(self, client: httpx.AsyncClient, repo_name: str) -> None:
        payload = {
            "name": repo_name,
            "description": f"Projeto criado pelo AI Office System — {repo_name}",
            "private": False,
            "auto_init": True,
        }
        resp = await client.post(f"{GITHUB_API}/user/repos", json=payload)
        resp.raise_for_status()

    async def _get_file_sha(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        path: str,
        branch: str,
    ) -> Optional[str]:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            params={"ref": branch},
        )
        if resp.status_code == 200:
            return resp.json().get("sha")
        return None

    def _resolve_repo_root(self, repo_path: str, *, init_repo_if_missing: bool = True) -> Path:
        if repo_path in {"", "."}:
            candidate = REPO_ROOT
        else:
            candidate = Path(repo_path).expanduser().resolve()
        if candidate.is_file():
            candidate = candidate.parent
        if not candidate.exists():
            raise RuntimeError(f"repo_path inexistente: {candidate}")

        if not self._is_allowed_repo(candidate):
            raise RuntimeError(f"repo_path fora das raizes autorizadas: {candidate}")

        result = self._git(candidate, ["rev-parse", "--show-toplevel"], check=False)
        if result.returncode != 0:
            if not init_repo_if_missing:
                raise RuntimeError(f"'{candidate}' não está dentro de um repositório git.")
            init_result = self._git(candidate, ["init"], check=False)
            if init_result.returncode != 0:
                message = (init_result.stderr or init_result.stdout or "").strip()
                raise RuntimeError(f"git init falhou em '{candidate}': {message}")
            result = self._git(candidate, ["rev-parse", "--show-toplevel"], check=False)
            if result.returncode != 0:
                raise RuntimeError(f"'{candidate}' não pôde ser inicializado como repositório git.")
        return Path(result.stdout.strip()).resolve()

    def _is_allowed_repo(self, candidate: Path) -> bool:
        try:
            candidate.relative_to(REPO_ROOT)
            return True
        except ValueError:
            pass
        try:
            relative = candidate.relative_to(GENERATED_PROJECTS_ROOT)
            if not relative.parts or relative.parts[0] == "_system":
                return False
            return True
        except ValueError:
            return False

    def _normalize_commit_path(self, repo_root: Path, path: str) -> str:
        raw = path.replace("\\", "/").strip().lstrip("/")
        target = (repo_root / raw).resolve()
        try:
            rel = target.relative_to(repo_root)
        except ValueError as exc:
            raise RuntimeError(f"path fora do repositorio autorizado: {path}") from exc
        parts = set(rel.parts)

        if parts & BLOCKED_COMMIT_PARTS:
            raise RuntimeError(f"path bloqueado para commit: {path}")
        if target.name in BLOCKED_COMMIT_FILES:
            raise RuntimeError(f"arquivo sensivel bloqueado para commit: {path}")
        return str(rel).replace("\\", "/")

    def _git(
        self,
        cwd: Path,
        args: list[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if check and result.returncode != 0:
            message = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(message or f"git {' '.join(args)} falhou")
        return result


class GitHubCreateRepoTool(BaseTool):
    """Cria repositório GitHub com estrutura inicial."""

    name: str = "github_create_repo"
    description: str = (
        "Cria um novo repositório no GitHub para hospedar um projeto. "
        "Use quando iniciar um novo projeto de desenvolvimento."
    )

    class CreateRepoInput(BaseModel):
        repo_name: str
        description: str = ""
        private: bool = False

    args_schema: type[BaseModel] = CreateRepoInput

    def _run(self, repo_name: str, description: str = "", private: bool = False) -> str:
        import asyncio

        return asyncio.run(self._create(repo_name, description, private))

    async def _create(self, repo_name: str, description: str, private: bool) -> str:
        headers = {
            "Authorization": f"token {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        payload = {
            "name": repo_name,
            "description": description or f"Projeto AI Office — {repo_name}",
            "private": private,
            "auto_init": True,
        }
        async with httpx.AsyncClient(headers=headers) as client:
            resp = await client.post(f"{GITHUB_API}/user/repos", json=payload)
            if resp.status_code == 422:
                return f"WARN: Repositorio '{repo_name}' ja existe."
            resp.raise_for_status()
            url = resp.json()["html_url"]
            return f"OK: Repositorio criado: {url}"


github_commit_tool = GitHubTool()
github_create_repo_tool = GitHubCreateRepoTool()
