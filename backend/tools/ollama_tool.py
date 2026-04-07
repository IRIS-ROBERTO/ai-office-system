"""
AI Office System — Ollama + OpenRouter LLM Bridge
Abstração unificada que redireciona chamadas para local (Ollama)
ou fallback (OpenRouter) de forma transparente.
"""
import logging
from typing import Optional
import httpx
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel

from backend.config.settings import settings

logger = logging.getLogger(__name__)


def get_local_llm(model: Optional[str] = None, temperature: float = 0.1) -> ChatOllama:
    """Retorna LLM local via Ollama — custo zero."""
    return ChatOllama(
        model=model or settings.LOCAL_MODEL_GENERAL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=temperature,
        num_predict=settings.LOCAL_MAX_TOKENS,
    )


def get_code_llm(temperature: float = 0.05) -> ChatOllama:
    """Qwen 2.5 Coder — melhor modelo local para código."""
    return get_local_llm(model=settings.LOCAL_MODEL_CODE, temperature=temperature)


def get_reasoning_llm(temperature: float = 0.1) -> ChatOllama:
    """DeepSeek R1 — raciocínio complexo e debugging."""
    return get_local_llm(model=settings.LOCAL_MODEL_REASONING, temperature=temperature)


def get_senior_llm(temperature: float = 0.2) -> ChatOpenAI:
    """
    Senior Agent — Claude Sonnet via OpenRouter.
    Chamado APENAS para: planejamento inicial + quality gate final.
    """
    return ChatOpenAI(
        model=settings.SENIOR_MODEL,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
        temperature=temperature,
        max_tokens=settings.SENIOR_MAX_TOKENS,
        default_headers={
            "HTTP-Referer": "https://ai-office-system.local",
            "X-Title": "AI Office System",
        },
    )


async def check_ollama_health() -> dict:
    """Verifica quais modelos estão disponíveis no Ollama local."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return {"status": "online", "models": models}
    except Exception as e:
        logger.warning(f"Ollama offline: {e}")

    return {"status": "offline", "models": []}


def get_llm_for_role(role: str) -> BaseChatModel:
    """
    Rota o LLM correto com base no role do agente.
    Mantém custo baixo: código → Qwen, raciocínio → DeepSeek, geral → Llama.
    """
    CODE_ROLES = {"frontend", "backend", "docs"}
    REASONING_ROLES = {"planner", "security", "qa", "strategy"}
    SENIOR_ROLES = {"orchestrator"}

    if role in CODE_ROLES:
        return get_code_llm()
    elif role in REASONING_ROLES:
        return get_reasoning_llm()
    elif role in SENIOR_ROLES:
        return get_senior_llm()
    else:
        return get_local_llm()
