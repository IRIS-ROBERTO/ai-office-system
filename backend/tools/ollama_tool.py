"""
AI Office System — LLM Bridge
Três camadas de execução, custo crescente:

  CAMADA 1 — Ollama local (custo zero absoluto, sem internet):
    qwen2.5-coder:32b   → código (Frontend, Backend, Planner)
    qwen3-vl:8b         → visão+raciocínio (QA, Security, Analytics)
    iris-comments       → documentação (modelo customizado)
    iris-fast           → tarefas rápidas (Social, SEO)
    llama3.1:8b         → texto geral (Research, Content, Strategy)

  CAMADA 2 — OpenRouter modelos gratuitos (internet, custo zero):
    qwen/qwen3-coder:free              → código via nuvem
    meta-llama/llama-3.3-70b-instruct:free → Senior Agent / orquestração
    nvidia/nemotron-3-super-120b-a12b:free → quality gate pesado

  CAMADA 3 — OpenRouter modelos pagos (bloqueados pelo ModelGate se caros):
    Apenas modelos com custo < $0.005/chamada e $0.10/dia
    Controlados explicitamente por backend/tools/model_gate.py
"""
import logging
from typing import Optional
import httpx
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel

from backend.config.settings import settings
from backend.tools.model_gate import gate, ModelNotAllowedError, BudgetExceededError

logger = logging.getLogger(__name__)


def get_openrouter_llm(model_id: str, agent_id: str = "unknown",
                       temperature: float = 0.1) -> ChatOpenAI:
    """
    Retorna LLM OpenRouter com validação obrigatória do ModelGate.
    Levanta ModelNotAllowedError se modelo não estiver na whitelist.
    Levanta BudgetExceededError se custo estimado ultrapassar limite.
    """
    gate.validate(model_id=model_id, agent_id=agent_id)   # trava de segurança
    return ChatOpenAI(
        model=model_id,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=temperature,
        max_tokens=settings.SENIOR_MAX_TOKENS,
        default_headers={
            "HTTP-Referer": "https://ai-office-system.local",
            "X-Title": "AI Office System",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Senior Agent — Gemini 2.0 Flash
# ─────────────────────────────────────────────────────────────────────────────

def get_senior_llm(temperature: float = 0.2) -> BaseChatModel:
    """
    Senior Agent — hierarquia de fallback com rotação de modelos gratuitos.

    Ordem de tentativa:
      1. OpenRouter free pool (rotação: 4 modelos gratuitos diferentes)
         → Se rate-limited no primeiro, tenta o próximo automaticamente
      2. Gemini 2.0 Flash (fallback cloud se OpenRouter indisponível)
      3. qwen2.5-coder:32b local (fallback offline total)
    """
    # Pool de modelos gratuitos — ordem de preferência
    FREE_POOL = [
        "google/gemma-4-31b-it:free",                   # Google, provedor diferente
        "nvidia/nemotron-3-super-120b-a12b:free",        # NVIDIA, 120B
        "meta-llama/llama-3.3-70b-instruct:free",        # Meta, 70B
        "qwen/qwen3-next-80b-a3b-instruct:free",         # Qwen, 80B MoE
    ]

    if settings.OPENROUTER_API_KEY:
        for model_id in FREE_POOL:
            try:
                gate.validate(model_id=model_id, agent_id="senior_orchestrator")
                logger.info("Senior Agent usando OpenRouter: %s", model_id)
                return ChatOpenAI(
                    model=model_id,
                    openai_api_key=settings.OPENROUTER_API_KEY,
                    openai_api_base="https://openrouter.ai/api/v1",
                    temperature=temperature,
                    max_tokens=settings.SENIOR_MAX_TOKENS,
                    default_headers={
                        "HTTP-Referer": "https://ai-office-system.local",
                        "X-Title": "AI Office System",
                    },
                )
            except (ModelNotAllowedError, BudgetExceededError) as e:
                logger.warning("Gate bloqueou %s: %s", model_id, e)
                continue

    if settings.GEMINI_API_KEY:
        logger.info("Senior Agent usando Gemini fallback")
        return ChatOpenAI(
            model=settings.GEMINI_MODEL,
            openai_api_key=settings.GEMINI_API_KEY,
            openai_api_base=settings.GEMINI_BASE_URL,
            temperature=temperature,
            max_tokens=settings.SENIOR_MAX_TOKENS,
        )

    logger.warning("Sem API externa — Senior Agent usando qwen2.5-coder:32b local")
    return get_local_llm(model=settings.LOCAL_MODEL_CODE, temperature=temperature)


# ─────────────────────────────────────────────────────────────────────────────
# Agentes Locais — Ollama
# ─────────────────────────────────────────────────────────────────────────────

def get_local_llm(model: Optional[str] = None, temperature: float = 0.1) -> ChatOllama:
    """Base factory para modelos Ollama."""
    return ChatOllama(
        model=model or settings.LOCAL_MODEL_GENERAL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=temperature,
        num_predict=settings.LOCAL_MAX_TOKENS,
    )


def get_code_llm(temperature: float = 0.05) -> ChatOllama:
    """qwen2.5-coder:32b — melhor modelo local para código (Frontend, Backend, Planner)."""
    return get_local_llm(model=settings.LOCAL_MODEL_CODE, temperature=temperature)


def get_vision_llm(temperature: float = 0.1) -> ChatOllama:
    """qwen3-vl:8b — visão + raciocínio (QA, Security, Analytics)."""
    return get_local_llm(model=settings.LOCAL_MODEL_VISION, temperature=temperature)


def get_docs_llm(temperature: float = 0.15) -> ChatOllama:
    """iris-comments — modelo customizado para documentação e comentários."""
    return get_local_llm(model=settings.LOCAL_MODEL_DOCS, temperature=temperature)


def get_fast_llm(temperature: float = 0.3) -> ChatOllama:
    """iris-fast — tarefas rápidas e frequentes (Social, SEO)."""
    return get_local_llm(model=settings.LOCAL_MODEL_FAST, temperature=temperature)


def get_general_llm(temperature: float = 0.2) -> ChatOllama:
    """llama3.1:8b — texto geral (Research, Content, Strategy)."""
    return get_local_llm(model=settings.LOCAL_MODEL_GENERAL, temperature=temperature)


# ─────────────────────────────────────────────────────────────────────────────
# Roteador por Role
# ─────────────────────────────────────────────────────────────────────────────

def get_llm_for_role(role: str) -> BaseChatModel:
    """
    Roteia o modelo correto por role do agente.
    Balanceia qualidade vs velocidade vs custo computacional.
    """
    routing = {
        # Dev Team
        "planner":   get_code_llm,        # Arquitetura exige raciocínio técnico preciso
        "frontend":  get_code_llm,        # Código React/TS de alta qualidade
        "backend":   get_code_llm,        # APIs + lógica de negócio
        "qa":        get_vision_llm,      # Pode analisar screenshots de UI também
        "security":  get_vision_llm,      # Análise de código + diagramas de fluxo
        "docs":      get_docs_llm,        # Modelo especializado em documentação

        # Marketing Team
        "research":  get_general_llm,     # Análise de texto longa
        "strategy":  get_general_llm,     # Planejamento estratégico
        "content":   get_general_llm,     # Escrita criativa
        "seo":       get_fast_llm,        # Tarefas estruturadas e rápidas
        "social":    get_fast_llm,        # Posts curtos, alta frequência
        "analytics": get_vision_llm,      # Pode analisar gráficos e dashboards

        # Senior
        "orchestrator": get_senior_llm,   # Gemini Flash — planejamento e validação
    }

    factory = routing.get(role, get_general_llm)
    return factory()


# ─────────────────────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────────────────────

async def check_ollama_health() -> dict:
    """Verifica Ollama e retorna modelos disponíveis com tamanhos."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                raw = resp.json().get("models", [])
                models = [
                    {
                        "name": m["name"],
                        "size_gb": round(m.get("size", 0) / 1e9, 1),
                    }
                    for m in raw
                ]
                return {"status": "online", "models": models, "count": len(models)}
    except Exception as e:
        logger.warning("Ollama offline: %s", e)

    return {"status": "offline", "models": [], "count": 0}


async def check_gemini_health() -> dict:
    """Verifica se a Gemini API está acessível."""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": settings.GEMINI_API_KEY},
            )
            if resp.status_code == 200:
                return {"status": "online", "model": settings.GEMINI_MODEL}
            return {"status": "error", "code": resp.status_code}
    except Exception as e:
        logger.warning("Gemini API inaccessível: %s", e)
        return {"status": "offline"}
