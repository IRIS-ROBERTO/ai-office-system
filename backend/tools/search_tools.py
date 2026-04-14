"""
IRIS AI Office System — Search & Scrape Tools
Gives every agent real web access: search + scraping.

DuckDuckGoSearchTool  — free, no API key, via duckduckgo-search package
ScrapeWebsiteTool     — fetches and strips HTML (from crewai-tools)
"""
import logging
from typing import Optional, Type

import requests
from crewai.tools import BaseTool
from crewai_tools import ScrapeWebsiteTool
from duckduckgo_search import DDGS
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── DuckDuckGo custom wrapper ────────────────────────────────────────────────

class _DDGInput(BaseModel):
    query: str = Field(description="Consulta de busca em linguagem natural")
    max_results: int = Field(default=6, description="Número máximo de resultados (1-10)")


class DuckDuckGoSearchTool(BaseTool):
    """
    Busca na web via DuckDuckGo.
    Gratuito, sem API key, cobertura global.
    Ideal para: pesquisa de mercado, CVEs, docs de frameworks, intel competitivo.
    """

    name: str = "web_search"
    description: str = (
        "Realiza busca na web via DuckDuckGo e retorna os melhores resultados com título, "
        "URL e snippet. Use para pesquisar informações atuais, CVEs, documentação, "
        "concorrentes ou qualquer tema que exija dados externos. Sem API key necessária."
    )
    args_schema: Type[BaseModel] = _DDGInput

    def _run(self, query: str, max_results: int = 6) -> str:
        max_results = max(1, min(max_results, 10))
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return f"Nenhum resultado encontrado para: '{query}'"

            lines = [f"🔍 Resultados para: {query}\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. **{r.get('title', 'Sem título')}**")
                lines.append(f"   URL: {r.get('href', '')}")
                lines.append(f"   {r.get('body', '')[:300]}")
                lines.append("")

            return "\n".join(lines)

        except Exception as exc:
            logger.warning("[DuckDuckGoSearchTool] Erro na busca: %s", exc)
            return f"Erro ao buscar '{query}': {exc}"


# ── Ready-to-inject instances ─────────────────────────────────────────────────

web_search_tool = DuckDuckGoSearchTool()
"""
Free web search via DuckDuckGo.
Use for: market research, CVE lookups, framework docs, competitor intel.
No API key required.
"""

scrape_website_tool = ScrapeWebsiteTool()
"""
Fetches and strips HTML from any URL, returning clean text.
Use for: reading competitor pages, downloading documentation,
         extracting structured data from landing pages.
"""

logger.debug("[search_tools] DuckDuckGoSearchTool + ScrapeWebsiteTool prontos.")
