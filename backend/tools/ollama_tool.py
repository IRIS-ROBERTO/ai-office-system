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
from backend.tools.brain_router import get_crewai_llm_for_role, get_langchain_llm_for_role

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
    Senior Agent — hierarquia de fallback inteligente.

    Ordem de tentativa:
      1. Ollama local (qwen2.5-coder:32b) — zero rate-limit, latência baixa
         quando Ollama disponível localmente
      2. OpenRouter free pool (4 modelos gratuitos, rotação por provedor)
      3. Gemini 2.0 Flash (fallback cloud final)
    """
    try:
        return get_langchain_llm_for_role(
            role="orchestrator",
            agent_id="orchestrator_senior_01",
            temperature=temperature,
        )
    except Exception as exc:
        logger.warning("BrainRouter indisponivel para Senior; usando fallback legado: %s", exc)

    import httpx as _httpx

    # 1. Ollama local — prioridade: velocidade de resposta > tamanho de parâmetros
    # Para planejamento (planning), modelos menores respondem mais rápido
    # e geram JSON de qualidade suficiente sem saturar GPU.
    # qwen2.5:7b → llama3.1:8b → llama3.2:3b → qwen3-vl:8b (pesado, só como último recurso local)
    SENIOR_LOCAL_PREFERENCE = [
        settings.LOCAL_MODEL_FALLBACK,       # qwen2.5:7b    — 4.7GB, rápido e preciso
        settings.LOCAL_MODEL_GENERAL,        # llama3.1:8b   — 4.9GB, ótimo para JSON
        settings.LOCAL_MODEL_FALLBACK_SMALL, # llama3.2:3b   — 2.0GB, muito rápido
        settings.LOCAL_MODEL_VISION,         # qwen3-vl:8b   — 6.1GB, último recurso local
    ]
    try:
        resp = _httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        if resp.status_code == 200:
            models_available = [m["name"] for m in resp.json().get("models", [])]
            for preferred in SENIOR_LOCAL_PREFERENCE:
                base_name = preferred.split(":")[0]
                if any(base_name in m for m in models_available):
                    logger.info("Senior Agent usando Ollama local: %s", preferred)
                    return get_local_llm(model=preferred, temperature=temperature)
    except Exception as e:
        logger.debug("Ollama nao acessivel para Senior: %s", e)

    # 2. OpenRouter free pool — rotação de provedores distintos
    FREE_POOL = [
        "meta-llama/llama-3.3-70b-instruct:free",        # Meta, 70B
        "nvidia/nemotron-3-super-120b-a12b:free",        # NVIDIA, 120B
        "qwen/qwen3-next-80b-a3b-instruct:free",         # Qwen, 80B MoE
        "google/gemma-4-31b-it:free",                    # Google, 31B
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

    # 3. Gemini fallback
    if settings.GEMINI_API_KEY:
        logger.info("Senior Agent usando Gemini fallback")
        return ChatOpenAI(
            model=settings.GEMINI_MODEL,
            openai_api_key=settings.GEMINI_API_KEY,
            openai_api_base=settings.GEMINI_BASE_URL,
            temperature=temperature,
            max_tokens=settings.SENIOR_MAX_TOKENS,
        )

    logger.warning("Sem API externa — Senior Agent usando local fallback small")
    return get_local_llm(model=settings.LOCAL_MODEL_FALLBACK, temperature=temperature)


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


def get_reasoning_llm(temperature: float = 0.05) -> ChatOllama:
    """
    Modelo de raciocínio estruturado — qwen3-vl:8b (cabe na VRAM disponível).
    Usado por: Planner, QA, Security, Analytics, Strategy.
    """
    return get_local_llm(model=settings.LOCAL_MODEL_VISION, temperature=temperature)


# ─────────────────────────────────────────────────────────────────────────────
# CrewAI-compatible LLM factory
# CrewAI ≥0.63 aceita string no formato LiteLLM: "ollama/model" ou crewai.LLM
# ─────────────────────────────────────────────────────────────────────────────

def get_crewai_llm_str(role: str = "general") -> str:
    """
    Retorna string no formato LiteLLM para uso direto em crewai.Agent(llm=...).
    Escolhe o modelo mais adequado ao role que cabe na VRAM disponível.

    Modelos disponíveis (confirmados < 12GB VRAM):
      qwen3-vl:8b        6.1GB  — visão + raciocínio
      llama3.1:8b        4.9GB  — texto geral
      qwen2.5:7b         4.7GB  — geral/código
      iris-fast:latest   2.1GB  — tarefas rápidas
      iris-comments:latest 2.0GB — documentação
      llama3.2:3b        2.0GB  — pequeno/rápido
    """
    base = settings.OLLAMA_BASE_URL  # http://127.0.0.1:11434
    routing = {
        # Dev Team
        "planner":   f"ollama/{settings.LOCAL_MODEL_FALLBACK}",
        "frontend":  f"ollama/{settings.LOCAL_MODEL_FALLBACK}",
        "backend":   f"ollama/{settings.LOCAL_MODEL_FALLBACK}",
        "qa":        f"ollama/qwen3-vl:8b",
        "security":  f"ollama/qwen3-vl:8b",
        "docs":      f"ollama/{settings.LOCAL_MODEL_DOCS}",   # iris-comments
        # Marketing Team
        # Marketing estava estourando VRAM com modelos maiores durante retries.
        # Usamos perfis mais leves para manter throughput e evitar stalls silenciosos.
        "research":  f"ollama/{settings.LOCAL_MODEL_FALLBACK}",  # qwen2.5:7b
        "strategy":  f"ollama/{settings.LOCAL_MODEL_FALLBACK}",  # qwen2.5:7b
        "content":   f"ollama/{settings.LOCAL_MODEL_FALLBACK}",  # qwen2.5:7b
        "seo":       f"ollama/{settings.LOCAL_MODEL_FAST}",     # iris-fast
        "social":    f"ollama/{settings.LOCAL_MODEL_FAST}",
        "analytics": f"ollama/qwen3-vl:8b",
    }
    return routing.get(role, f"ollama/{settings.LOCAL_MODEL_FALLBACK}")


def get_crewai_llm_for_agent(role: str = "general", agent_id: str = "unknown"):
    """Retorna LLM CrewAI via BrainRouter com fallback local legado."""
    try:
        return get_crewai_llm_for_role(role=role, agent_id=agent_id)
    except Exception as exc:
        logger.warning(
            "BrainRouter indisponivel para %s/%s; usando Ollama local: %s",
            role,
            agent_id,
            exc,
        )
        return get_crewai_llm_str(role)


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
