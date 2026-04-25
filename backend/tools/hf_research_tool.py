"""
AI Office System — HuggingFace Research Tool
Raspa HuggingFace Hub em busca de modelos e datasets promissores.

Foca em:
  - Modelos LLM (text-generation, conversational)
  - Modelos de embedding (feature-extraction)
  - Datasets relevantes para AI agents / RAG
  - Spaces inovadores
"""
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HF_API = "https://huggingface.co/api"

RELEVANT_TAGS = {
    "text-generation", "conversational", "feature-extraction",
    "question-answering", "summarization", "translation",
    "zero-shot-classification", "text-classification",
    "reinforcement-learning", "agents",
}

PRIORITY_TAGS = {"text-generation", "conversational", "feature-extraction"}


def _score_hf_model(model: dict) -> dict[str, Any]:
    """Score multidimensional para modelos HuggingFace."""
    downloads = model.get("downloads", 0) or 0
    likes = model.get("likes", 0) or 0
    tags: list[str] = model.get("tags") or []
    pipeline_tag = model.get("pipeline_tag") or ""
    last_modified = model.get("lastModified") or model.get("updatedAt") or ""

    # Score de popularidade por downloads (0-30)
    if downloads >= 1_000_000:
        dl_score = 30
    elif downloads >= 100_000:
        dl_score = 25
    elif downloads >= 10_000:
        dl_score = 18
    elif downloads >= 1_000:
        dl_score = 12
    elif downloads >= 100:
        dl_score = 6
    else:
        dl_score = 2

    # Score de likes (0-20)
    if likes >= 5000:
        like_score = 20
    elif likes >= 1000:
        like_score = 15
    elif likes >= 200:
        like_score = 10
    elif likes >= 50:
        like_score = 5
    else:
        like_score = 1

    # Score de pipeline relevante (0-25)
    pipeline_score = 20 if pipeline_tag in PRIORITY_TAGS else (12 if pipeline_tag in RELEVANT_TAGS else 4)

    # Score de atividade recente (0-15)
    activity_score = 0
    if last_modified:
        try:
            mod = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - mod).days
            if days <= 30:
                activity_score = 15
            elif days <= 90:
                activity_score = 10
            elif days <= 180:
                activity_score = 5
        except Exception:
            pass

    # Bônus por tags especiais (0-10)
    bonus = 0
    bonus_tags = {"agents", "gguf", "quantized", "instruct", "chat", "function-calling"}
    for tag in tags:
        if any(bt in tag.lower() for bt in bonus_tags):
            bonus = min(10, bonus + 3)

    total = dl_score + like_score + pipeline_score + activity_score + bonus

    if total >= 65:
        grade, grade_label = "S", "Excepcional"
    elif total >= 50:
        grade, grade_label = "A", "Alto potencial"
    elif total >= 35:
        grade, grade_label = "B", "Promissor"
    elif total >= 20:
        grade, grade_label = "C", "Relevante"
    else:
        grade, grade_label = "D", "Monitorar"

    # Potencial de aplicação
    iris_fit_tags = []
    if pipeline_tag in {"text-generation", "conversational"}:
        iris_fit_tags.append("LLM / Geração de texto")
    if pipeline_tag == "feature-extraction":
        iris_fit_tags.append("Embeddings / RAG")
    if "agents" in tags or "function-calling" in (t.lower() for t in tags):
        iris_fit_tags.append("Agentes / Tool Use")
    if "gguf" in tags or "quantized" in tags:
        iris_fit_tags.append("Modelos locais (Ollama)")
    if not iris_fit_tags:
        iris_fit_tags.append("Pesquisa geral HF")

    return {
        "score": total,
        "grade": grade,
        "grade_label": grade_label,
        "breakdown": {
            "downloads": dl_score,
            "likes": like_score,
            "pipeline_relevancia": pipeline_score,
            "atividade_recente": activity_score,
            "bonus_tags": bonus,
        },
        "iris_fit": iris_fit_tags,
        "downloads": downloads,
        "likes": likes,
        "pipeline_tag": pipeline_tag,
        "tags": tags[:20],
    }


async def search_hf_models(
    queries: list[str] | None = None,
    limit_per_query: int = 8,
) -> list[dict[str, Any]]:
    """
    Busca modelos promissores no HuggingFace Hub.
    """
    if queries is None:
        queries = [
            "agent",
            "function calling",
            "instruct",
            "local llm",
            "embedding",
        ]

    seen_ids: set[str] = set()
    findings: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for query in queries:
            try:
                resp = await client.get(
                    f"{HF_API}/models",
                    params={
                        "search": query,
                        "sort": "downloads",
                        "direction": -1,
                        "limit": limit_per_query,
                        "full": True,
                    },
                )
                resp.raise_for_status()
                models = resp.json()

                for model in models:
                    model_id: str = model.get("modelId") or model.get("id") or ""
                    if not model_id or model_id in seen_ids:
                        continue
                    seen_ids.add(model_id)

                    score_data = _score_hf_model(model)
                    findings.append({
                        "id": f"hf_{model_id.replace('/', '__')}",
                        "source": "huggingface",
                        "name": model_id,
                        "title": model_id.split("/")[-1] if "/" in model_id else model_id,
                        "description": model.get("description") or f"HuggingFace model: {model_id}",
                        "url": f"https://huggingface.co/{model_id}",
                        "author": model_id.split("/")[0] if "/" in model_id else "unknown",
                        "created_at": model.get("createdAt") or "",
                        "updated_at": model.get("lastModified") or model.get("updatedAt") or "",
                        "pushed_at": model.get("lastModified") or model.get("updatedAt") or "",
                        "language": "N/A",
                        "license": model.get("license") or "N/A",
                        "query_used": query,
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        **score_data,
                    })
            except httpx.HTTPError as exc:
                logger.warning(f"[HFResearch] Erro na busca '{query}': {exc}")
                continue

    findings.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"[HFResearch] {len(findings)} modelos encontrados.")
    return findings


async def search_hf_spaces(limit: int = 10) -> list[dict[str, Any]]:
    """Busca Spaces inovadores no HuggingFace."""
    findings: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(
                f"{HF_API}/spaces",
                params={"sort": "likes", "direction": -1, "limit": limit, "full": True},
            )
            resp.raise_for_status()
            spaces = resp.json()

            for space in spaces:
                space_id: str = space.get("id") or ""
                if not space_id:
                    continue

                likes = space.get("likes", 0) or 0
                score = min(80, likes // 10 + 20)

                findings.append({
                    "id": f"hf_space_{space_id.replace('/', '__')}",
                    "source": "huggingface_space",
                    "name": space_id,
                    "title": space_id.split("/")[-1] if "/" in space_id else space_id,
                    "description": space.get("description") or f"HuggingFace Space: {space_id}",
                    "url": f"https://huggingface.co/spaces/{space_id}",
                    "author": space_id.split("/")[0] if "/" in space_id else "unknown",
                    "created_at": space.get("createdAt") or "",
                    "updated_at": space.get("lastModified") or "",
                    "pushed_at": space.get("lastModified") or "",
                    "language": "N/A",
                    "license": "N/A",
                    "query_used": "spaces_trending",
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "score": score,
                    "grade": "A" if score >= 55 else "B",
                    "grade_label": "Space popular",
                    "breakdown": {"likes": likes},
                    "iris_fit": ["UI / Demo de IA"],
                    "downloads": 0,
                    "likes": likes,
                    "pipeline_tag": "space",
                    "tags": [],
                })
        except httpx.HTTPError as exc:
            logger.warning(f"[HFResearch] Erro ao buscar spaces: {exc}")

    return findings
