"""
AI Office System — GitHub Tool
Ferramenta que TODOS os agentes usam para commitar e criar repositórios.
Quando um agente termina um entregável, ele mesmo commita no GitHub.
"""
import base64
import logging
from pathlib import Path
from typing import Optional
import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.core.event_types import OfficialEvent, EventType, TeamType, AgentRole

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubCommitInput(BaseModel):
    repo_name: str = Field(description="Nome do repositório (ex: 'meu-projeto')")
    file_path: str = Field(description="Caminho do arquivo no repo (ex: 'src/main.py')")
    content: str = Field(description="Conteúdo completo do arquivo")
    commit_message: str = Field(description="Mensagem de commit descritiva")
    branch: str = Field(default="main", description="Branch alvo")
    create_repo_if_missing: bool = Field(default=True)


class GitHubTool(BaseTool):
    """
    Permite que agentes criem repositórios, committam código e façam push
    autonomamente — sem intervenção humana.
    """
    name: str = "github_commit"
    description: str = (
        "Commita arquivos no GitHub. Se o repositório não existir, cria automaticamente. "
        "Use após completar qualquer entregável (código, conteúdo, documentação)."
    )
    args_schema: type[BaseModel] = GitHubCommitInput

    def _run(
        self,
        repo_name: str,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str = "main",
        create_repo_if_missing: bool = True,
    ) -> str:
        import asyncio
        return asyncio.run(
            self._async_commit(repo_name, file_path, content, commit_message, branch, create_repo_if_missing)
        )

    async def _async_commit(
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
            # 1. Verifica se repo existe
            repo_exists = await self._check_repo(client, owner, repo_name)

            if not repo_exists and create_repo_if_missing:
                await self._create_repo(client, owner, repo_name)
                logger.info(f"Repositório '{repo_name}' criado no GitHub")

            # 2. Obtém SHA atual do arquivo (para update)
            sha = await self._get_file_sha(client, owner, repo_name, file_path, branch)

            # 3. Commita
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
            logger.info(f"Commit realizado: {commit_url}")
            return f"✅ Commit realizado: {commit_url}"

    async def _check_repo(self, client: httpx.AsyncClient, owner: str, repo: str) -> bool:
        resp = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}")
        return resp.status_code == 200

    async def _create_repo(self, client: httpx.AsyncClient, owner: str, repo_name: str):
        payload = {
            "name": repo_name,
            "description": f"Projeto criado pelo AI Office System — {repo_name}",
            "private": False,
            "auto_init": True,
        }
        resp = await client.post(f"{GITHUB_API}/user/repos", json=payload)
        resp.raise_for_status()

    async def _get_file_sha(
        self, client: httpx.AsyncClient, owner: str, repo: str, path: str, branch: str
    ) -> Optional[str]:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            params={"ref": branch},
        )
        if resp.status_code == 200:
            return resp.json().get("sha")
        return None


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
                return f"⚠️ Repositório '{repo_name}' já existe."
            resp.raise_for_status()
            url = resp.json()["html_url"]
            return f"✅ Repositório criado: {url}"


# Instâncias prontas para injetar nos agentes
github_commit_tool = GitHubTool()
github_create_repo_tool = GitHubCreateRepoTool()
