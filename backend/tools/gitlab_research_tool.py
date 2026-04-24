"""
AI Office System - GitLab Research Tool

Public GitLab project discovery for SCOUT. The output mirrors the GitHub and
HuggingFace finding contract so insights can rank market signals uniformly.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx


logger = logging.getLogger(__name__)

GITLAB_API = "https://gitlab.com/api/v4"

RELEVANT_TOPICS = {
    "ai",
    "llm",
    "agent",
    "agents",
    "automation",
    "workflow",
    "rag",
    "mcp",
    "machine-learning",
    "developer-tools",
    "devops",
    "api",
    "python",
}


def _score_project(project: dict[str, Any]) -> dict[str, Any]:
    stars = int(project.get("star_count") or 0)
    forks = int(project.get("forks_count") or 0)
    topics = [str(item).lower() for item in (project.get("topics") or project.get("tag_list") or [])]
    description = project.get("description") or ""
    last_activity_at = project.get("last_activity_at") or ""

    if stars >= 5000:
        pop_score = 30
    elif stars >= 1000:
        pop_score = 24
    elif stars >= 500:
        pop_score = 18
    elif stars >= 100:
        pop_score = 12
    elif stars >= 25:
        pop_score = 7
    else:
        pop_score = 3

    topic_hits = sum(1 for topic in topics if topic in RELEVANT_TOPICS)
    topic_score = min(25, topic_hits * 5)

    activity_score = 0
    if last_activity_at:
        try:
            last_activity = datetime.fromisoformat(last_activity_at.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - last_activity).days
            if days <= 14:
                activity_score = 20
            elif days <= 45:
                activity_score = 15
            elif days <= 120:
                activity_score = 10
            elif days <= 240:
                activity_score = 5
        except Exception:
            pass

    desc_score = min(10, len(description) // 24) if description else 0
    fork_score = min(10, forks // 25)
    total = pop_score + topic_score + activity_score + desc_score + fork_score

    if total >= 70:
        grade, grade_label = "S", "Excepcional"
    elif total >= 55:
        grade, grade_label = "A", "Alto potencial"
    elif total >= 40:
        grade, grade_label = "B", "Promissor"
    elif total >= 25:
        grade, grade_label = "C", "Relevante"
    else:
        grade, grade_label = "D", "Monitorar"

    iris_fit: list[str] = []
    if any(topic in topics for topic in {"agent", "agents", "automation", "workflow"}):
        iris_fit.append("Automação de workflows")
    if any(topic in topics for topic in {"llm", "ai", "machine-learning"}):
        iris_fit.append("Integração LLM")
    if any(topic in topics for topic in {"rag", "mcp"}):
        iris_fit.append("MCP / Ferramentas")
    if any(topic in topics for topic in {"api", "python", "developer-tools", "devops"}):
        iris_fit.append("Ferramentas para Devs")
    if not iris_fit:
        iris_fit.append("Pesquisa geral GitLab")

    return {
        "score": total,
        "grade": grade,
        "grade_label": grade_label,
        "breakdown": {
            "popularidade": pop_score,
            "relevancia_topics": topic_score,
            "atividade_recente": activity_score,
            "qualidade_descricao": desc_score,
            "forks": fork_score,
        },
        "iris_fit": iris_fit,
        "stars": stars,
        "forks": forks,
        "topics": topics,
    }


def _build_finding(project: dict[str, Any], query: str) -> dict[str, Any]:
    score_data = _score_project(project)
    namespace = project.get("path_with_namespace") or project.get("name_with_namespace") or ""
    return {
        "id": f"gl_{project.get('id')}",
        "source": "gitlab",
        "name": namespace,
        "title": project.get("name") or namespace,
        "description": project.get("description") or "",
        "url": project.get("web_url") or "",
        "language": "N/A",
        "license": "N/A",
        "created_at": project.get("created_at") or "",
        "updated_at": project.get("last_activity_at") or "",
        "pushed_at": project.get("last_activity_at") or "",
        "query_used": query,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        **score_data,
    }


async def search_gitlab_projects(
    queries: list[str] | None = None,
    min_stars: int = 25,
    days_back: int = 60,
    per_query: int = 12,
) -> list[dict[str, Any]]:
    """Search public GitLab projects and return SCOUT-compatible findings."""
    if queries is None:
        queries = [
            "ai agent",
            "llm workflow",
            "rag",
            "automation",
            "developer tool",
        ]

    last_activity_after = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    seen_ids: set[int] = set()
    findings: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=25.0) as client:
        for query in queries:
            try:
                response = await client.get(
                    f"{GITLAB_API}/projects",
                    params={
                        "search": query,
                        "order_by": "star_count",
                        "sort": "desc",
                        "simple": "true",
                        "per_page": per_query,
                        "last_activity_after": last_activity_after,
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("[GitLabResearch] HTTP error para '%s': %s", query, exc)
                continue

            for project in response.json():
                project_id = project.get("id")
                if not project_id or project_id in seen_ids:
                    continue
                if int(project.get("star_count") or 0) < min_stars:
                    continue
                seen_ids.add(project_id)
                findings.append(_build_finding(project, query))

    findings.sort(key=lambda item: item.get("score", 0), reverse=True)
    logger.info("[GitLabResearch] %d projetos GitLab encontrados.", len(findings))
    return findings
