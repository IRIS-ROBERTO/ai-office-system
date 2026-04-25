"""
AI Office System — GitHub Research Tool
Ferramenta de inteligência técnica: raspa GitHub em busca de projetos promissores.

Critérios de score:
  - Stars / crescimento recente
  - Relevância de topics (AI, LLM, agent, automation)
  - Qualidade do README (tamanho como proxy)
  - Atividade recente (commits, releases)
  - Potencial de combinação com o stack IRIS
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

from backend.config.settings import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
RELEVANT_TOPICS = {
    "llm", "ai", "agent", "agents", "langchain", "langgraph", "crewai",
    "openai", "ollama", "fastapi", "automation", "autonomous", "rag",
    "multiagent", "copilot", "workflow", "orchestration", "chatbot",
    "nlp", "gpt", "claude", "anthropic", "embeddings", "vector-db",
    "mcp", "model-context-protocol", "function-calling", "tool-use",
    "ai-agents", "ai-assistant", "llm-agent", "agentic", "huggingface",
}

HIGH_VALUE_TOPICS = {"agent", "agents", "multiagent", "orchestration", "llm", "mcp", "ai-agents", "agentic"}

# Topic-based queries using GitHub's topic: qualifier — very precise results
TOPIC_QUERIES = [
    "topic:llm-agent",
    "topic:ai-agents",
    "topic:model-context-protocol",
    "topic:agentic",
    "topic:multiagent",
    "topic:langgraph",
    "topic:crewai",
    "topic:rag language:python",
    "topic:function-calling",
    "topic:llm language:python",
]


def _score_project(repo: dict) -> dict[str, Any]:
    """Calcula score multidimensional de um repositório GitHub."""
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    open_issues = repo.get("open_issues_count", 0)
    topics: list[str] = repo.get("topics") or []
    description = repo.get("description") or ""
    pushed_at = repo.get("pushed_at") or ""
    created_at = repo.get("created_at") or ""

    # Score de popularidade (0-30)
    if stars >= 10000:
        pop_score = 30
    elif stars >= 5000:
        pop_score = 25
    elif stars >= 1000:
        pop_score = 20
    elif stars >= 500:
        pop_score = 15
    elif stars >= 100:
        pop_score = 10
    elif stars >= 20:
        pop_score = 5
    else:
        pop_score = 2

    # Score de relevância de topics (0-25)
    topic_hits = sum(1 for t in topics if t in RELEVANT_TOPICS)
    high_value_hits = sum(1 for t in topics if t in HIGH_VALUE_TOPICS)
    topic_score = min(15, topic_hits * 3) + min(10, high_value_hits * 5)

    # Score de atividade recente (0-20)
    activity_score = 0
    if pushed_at:
        try:
            pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            days_since_push = (datetime.now(timezone.utc) - pushed).days
            if days_since_push <= 7:
                activity_score = 20
            elif days_since_push <= 30:
                activity_score = 15
            elif days_since_push <= 90:
                activity_score = 10
            elif days_since_push <= 180:
                activity_score = 5
        except Exception:
            pass

    # Score de novidade (0-15) — projetos recentes ganham bônus
    novelty_score = 0
    if created_at:
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            days_since_creation = (datetime.now(timezone.utc) - created).days
            if days_since_creation <= 90:
                novelty_score = 15
            elif days_since_creation <= 180:
                novelty_score = 10
            elif days_since_creation <= 365:
                novelty_score = 5
        except Exception:
            pass

    # Score de descrição (0-10)
    desc_score = min(10, len(description) // 20) if description else 0

    total = pop_score + topic_score + activity_score + novelty_score + desc_score

    # Classificação
    if total >= 70:
        grade = "S"
        grade_label = "Excepcional"
    elif total >= 55:
        grade = "A"
        grade_label = "Alto potencial"
    elif total >= 40:
        grade = "B"
        grade_label = "Promissor"
    elif total >= 25:
        grade = "C"
        grade_label = "Relevante"
    else:
        grade = "D"
        grade_label = "Monitorar"

    # Potencial de aplicação no IRIS
    iris_fit_tags = []
    if any(t in topics for t in {"agent", "agents", "multiagent", "orchestration"}):
        iris_fit_tags.append("Orquestração de agentes")
    if any(t in topics for t in {"llm", "ollama", "openai", "claude", "anthropic"}):
        iris_fit_tags.append("Integração LLM")
    if any(t in topics for t in {"fastapi", "api", "rest"}):
        iris_fit_tags.append("Backend API")
    if any(t in topics for t in {"rag", "embeddings", "vector-db"}):
        iris_fit_tags.append("RAG / Memória")
    if any(t in topics for t in {"mcp", "model-context-protocol"}):
        iris_fit_tags.append("MCP / Ferramentas")
    if any(t in topics for t in {"workflow", "automation", "n8n"}):
        iris_fit_tags.append("Automação de workflows")
    if not iris_fit_tags:
        iris_fit_tags.append("Pesquisa geral")

    return {
        "score": total,
        "grade": grade,
        "grade_label": grade_label,
        "breakdown": {
            "popularidade": pop_score,
            "relevancia_topics": topic_score,
            "atividade_recente": activity_score,
            "novidade": novelty_score,
            "qualidade_descricao": desc_score,
        },
        "iris_fit": iris_fit_tags,
        "stars": stars,
        "forks": forks,
        "open_issues": open_issues,
        "topics": topics,
    }


def _build_finding(repo: dict, query: str) -> dict[str, Any]:
    """Constrói um finding padronizado a partir de um repo da API GitHub."""
    score_data = _score_project(repo)
    return {
        "id": f"gh_{repo['id']}",
        "source": "github",
        "name": repo.get("full_name", ""),
        "title": repo.get("name", ""),
        "description": repo.get("description") or "",
        "url": repo.get("html_url", ""),
        "language": repo.get("language") or "N/A",
        "license": (repo.get("license") or {}).get("spdx_id") or "N/A",
        "created_at": repo.get("created_at") or "",
        "updated_at": repo.get("updated_at") or "",
        "pushed_at": repo.get("pushed_at") or "",
        "query_used": query,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        **score_data,
    }


async def _fetch_page(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    q: str,
    per_page: int = 30,
) -> list[dict]:
    """Faz uma request paginada para a Search API do GitHub."""
    try:
        resp = await client.get(
            f"{GITHUB_API}/search/repositories",
            params={"q": q, "sort": "stars", "order": "desc", "per_page": per_page},
            headers=headers,
        )
        if resp.status_code == 403:
            logger.warning("[GitHubResearch] Rate limit atingido (403). Token configurado?")
            return []
        if resp.status_code == 422:
            logger.warning(f"[GitHubResearch] Query inválida (422): {q}")
            return []
        resp.raise_for_status()
        return resp.json().get("items", [])
    except httpx.HTTPError as exc:
        logger.warning(f"[GitHubResearch] HTTP error para '{q}': {exc}")
        return []


async def search_github_trending(
    queries: list[str] | None = None,
    min_stars: int = 50,
    days_back: int = 30,
    per_query: int = 15,
    github_token: str | None = None,
) -> list[dict[str, Any]]:
    """
    Busca repositórios promissores no GitHub via Search API (autenticada).
    Combina queries de texto livre + topic: qualifiers para cobertura máxima.
    Rate limit autenticado: 5000 req/hora, 30 req/min para search.
    """
    if queries is None:
        queries = [
            "AI agent orchestration",
            "LLM multi-agent framework",
            "crewai langgraph",
            "autonomous AI workflow",
            "model context protocol MCP",
            "local LLM ollama agent",
        ]

    token = github_token or getattr(settings, "GITHUB_TOKEN", None) or ""
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        logger.info("[GitHubResearch] Usando token autenticado (5000 req/hora, 30 req/min search).")
    else:
        logger.warning("[GitHubResearch] Sem token — limite de 10 req/min. Configure GITHUB_TOKEN no .env")

    since_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    seen_ids: set[int] = set()
    findings: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=25.0) as client:
        # 1. Queries de texto livre com qualificadores de stars e data
        for query in queries:
            q = f"{query} stars:>={min_stars} pushed:>={since_date}"
            items = await _fetch_page(client, headers, q, per_query)
            for repo in items:
                rid = repo.get("id")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    findings.append(_build_finding(repo, query))

        # 2. Topic-based queries — resultados mais precisos (repos auto-categorizados)
        for tq in TOPIC_QUERIES:
            q = f"{tq} stars:>={min_stars} pushed:>={since_date}"
            items = await _fetch_page(client, headers, q, per_query)
            for repo in items:
                rid = repo.get("id")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    findings.append(_build_finding(repo, tq))

    findings.sort(key=lambda x: x["score"], reverse=True)
    logger.info(
        f"[GitHubResearch] {len(findings)} projetos únicos em "
        f"{len(queries)} queries texto + {len(TOPIC_QUERIES)} topic queries."
    )
    return findings


async def analyze_combination_potential(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Analisa potencial de combinação entre projetos.
    Detecta projetos complementares que poderiam ser integrados.
    """
    combinations = []

    backend_tools = [f for f in findings if any(t in f.get("topics", []) for t in {"fastapi", "api", "backend"})]
    agent_frameworks = [f for f in findings if any(t in f.get("topics", []) for t in {"agent", "agents", "orchestration"})]
    llm_tools = [f for f in findings if any(t in f.get("topics", []) for t in {"llm", "ollama", "openai"})]
    memory_tools = [f for f in findings if any(t in f.get("topics", []) for t in {"rag", "embeddings", "vector-db", "memory"})]

    # Combina agent frameworks com LLM tools
    for agent in agent_frameworks[:3]:
        for llm in llm_tools[:3]:
            if agent["id"] != llm["id"]:
                combo_score = int((agent["score"] + llm["score"]) * 0.6)
                combo_title = f"{agent['title']} + {llm['title']}"
                combinations.append({
                    "id": f"combo_{agent['id']}_{llm['id']}",
                    "source": "combination",
                    "name": f"{agent['name']} + {llm['name']}",
                    "title": combo_title,
                    "url": agent.get("url", ""),
                    "type": "combination",
                    "description": f"Combinação: framework de agentes + integração LLM. {(agent.get('description') or '')[:120]}",
                    "language": "N/A",
                    "projects": [agent["id"], llm["id"]],
                    "project_names": [agent["name"], llm["name"]],
                    "score": combo_score,
                    "grade": "A" if combo_score >= 55 else "B",
                    "grade_label": "Combinação promissora",
                    "iris_fit": ["Orquestração de agentes", "Integração LLM"],
                    "combination_rationale": "Agent framework + LLM provider = stack completo de agentes autônomos",
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "breakdown": {},
                    "topics": [],
                    "tags": [],
                    "stars": 0,
                    "forks": 0,
                    "downloads": 0,
                    "likes": 0,
                })

    # Combina memory tools com agent frameworks
    for mem in memory_tools[:2]:
        for agent in agent_frameworks[:2]:
            if mem["id"] != agent["id"]:
                combo_score = int((mem["score"] + agent["score"]) * 0.55)
                combinations.append({
                    "id": f"combo_{mem['id']}_{agent['id']}",
                    "source": "combination",
                    "name": f"{mem['name']} + {agent['name']}",
                    "title": f"{mem['title']} + {agent['title']}",
                    "url": mem.get("url", ""),
                    "type": "combination",
                    "description": "Combinação: sistema de memória + orquestrador. Potencial para agentes com memória persistente.",
                    "language": "N/A",
                    "projects": [mem["id"], agent["id"]],
                    "project_names": [mem["name"], agent["name"]],
                    "score": combo_score,
                    "grade": "A" if combo_score >= 55 else "B",
                    "grade_label": "Combinação promissora",
                    "iris_fit": ["RAG / Memória", "Orquestração de agentes"],
                    "combination_rationale": "Memória vetorial + agentes = sistema com contexto persistente e aprendizado",
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "breakdown": {},
                    "topics": [],
                    "tags": [],
                    "stars": 0,
                    "forks": 0,
                    "downloads": 0,
                    "likes": 0,
                })

    combinations.sort(key=lambda x: x["score"], reverse=True)
    return combinations[:10]
