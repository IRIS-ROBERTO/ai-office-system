"""
IRIS AI Office System — NotionWriteTool
Gives LORE (Docs), NOVA (Content), MAVEN (Strategy), PRISM (Analytics)
the ability to publish deliverables directly to Notion.

Operations:
  - create_page  : Create a new page under a parent page/database
  - append_block : Append markdown content to an existing page
  - search_page  : Search for a Notion page by title

Requirements:
  NOTION_TOKEN=secret_xxxxxx  (from Notion Integrations)
  NOTION_DEFAULT_PARENT_ID=<parent page or database UUID>
"""
import json
import logging
from typing import Optional, Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from backend.config.settings import settings

logger = logging.getLogger(__name__)

_NOTION_API = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


class NotionWriteInput(BaseModel):
    operation: str = Field(
        description="Operação: 'create_page', 'append_block', ou 'search_page'"
    )
    title: str = Field(default="", description="Título da página (para create_page)")
    content: str = Field(default="", description="Conteúdo em texto/markdown")
    parent_id: Optional[str] = Field(
        default=None,
        description="ID da página/database pai (usa NOTION_DEFAULT_PARENT_ID se omitido)",
    )
    page_id: Optional[str] = Field(
        default=None,
        description="ID da página a ser atualizada (para append_block)",
    )
    query: Optional[str] = Field(
        default=None,
        description="Texto de busca (para search_page)",
    )


class NotionWriteTool(BaseTool):
    """
    Publica conteúdo diretamente no Notion.
    LORE usa para documentação técnica; NOVA usa para artigos de blog;
    MAVEN usa para estratégias; PRISM usa para relatórios de analytics.
    """

    name: str = "notion_write"
    description: str = (
        "Publica e atualiza páginas no Notion. "
        "Use para criar documentação, artigos, estratégias e relatórios. "
        "Operações: create_page (cria nova página), "
        "append_block (adiciona conteúdo a página existente), "
        "search_page (busca página por título)."
    )
    args_schema: Type[BaseModel] = NotionWriteInput

    def _headers(self) -> dict:
        token = getattr(settings, "NOTION_TOKEN", "")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": _NOTION_VERSION,
        }

    def _run(
        self,
        operation: str,
        title: str = "",
        content: str = "",
        parent_id: Optional[str] = None,
        page_id: Optional[str] = None,
        query: Optional[str] = None,
    ) -> str:
        token = getattr(settings, "NOTION_TOKEN", "")
        if not token:
            return (
                "⚠️ NOTION_TOKEN não configurado. "
                "Adicione NOTION_TOKEN=secret_xxx no .env para habilitar publicação no Notion."
            )

        try:
            if operation == "search_page":
                return self._search_page(query or title)
            elif operation == "create_page":
                pid = parent_id or getattr(settings, "NOTION_DEFAULT_PARENT_ID", "")
                return self._create_page(title, content, pid)
            elif operation == "append_block":
                if not page_id:
                    return "❌ page_id é obrigatório para append_block."
                return self._append_blocks(page_id, content)
            else:
                return f"❌ Operação desconhecida: '{operation}'. Use: create_page, append_block, search_page."
        except Exception as exc:
            logger.error("[NotionWriteTool] Erro: %s", exc)
            return f"❌ Erro no Notion: {exc}"

    def _search_page(self, query: str) -> str:
        resp = httpx.post(
            f"{_NOTION_API}/search",
            headers=self._headers(),
            json={"query": query, "filter": {"value": "page", "property": "object"}},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return f"Nenhuma página encontrada para '{query}'."
        pages = [
            {"id": r["id"], "title": r.get("properties", {}).get("title", {}).get("title", [{}])[0].get("plain_text", "sem título")}
            for r in results[:5]
        ]
        return f"✅ Páginas encontradas:\n{json.dumps(pages, ensure_ascii=False, indent=2)}"

    def _create_page(self, title: str, content: str, parent_id: str) -> str:
        if not parent_id:
            return "❌ parent_id não definido. Configure NOTION_DEFAULT_PARENT_ID no .env."

        # Convert content to paragraph blocks
        blocks = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": line[:2000]}}]
                },
            }
            for line in content.split("\n\n")[:50]
            if line.strip()
        ]

        body = {
            "parent": {"page_id": parent_id},
            "properties": {
                "title": {"title": [{"text": {"content": title[:255]}}]}
            },
            "children": blocks,
        }

        resp = httpx.post(f"{_NOTION_API}/pages", headers=self._headers(), json=body, timeout=20)
        resp.raise_for_status()
        page = resp.json()
        page_url = page.get("url", "")
        logger.info("[NotionWriteTool] Página criada: %s", page_url)
        return f"✅ Página '{title}' criada no Notion: {page_url}"

    def _append_blocks(self, page_id: str, content: str) -> str:
        blocks = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": line[:2000]}}]
                },
            }
            for line in content.split("\n\n")[:50]
            if line.strip()
        ]

        resp = httpx.patch(
            f"{_NOTION_API}/blocks/{page_id}/children",
            headers=self._headers(),
            json={"children": blocks},
            timeout=20,
        )
        resp.raise_for_status()
        return f"✅ {len(blocks)} blocos adicionados à página {page_id}."


# Ready-to-inject instance
notion_write_tool = NotionWriteTool()
