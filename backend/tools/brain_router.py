"""
Brain Router for IRIS agents.

Selects the best available brain per role using this priority:
1. OpenRouter free models verified through the public catalog.
2. Local Ollama fallback, scoped by role.

The router is deliberately conservative: paid models are not selected here.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from crewai import LLM
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from backend.config.settings import settings
from backend.tools.model_gate import gate

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class BrainProfile:
    role: str
    purpose: str
    openrouter_candidates: tuple[str, ...]
    local_model: str
    temperature: float = 0.1
    max_tokens: int = 2048
    require_tools: bool = True
    require_structured: bool = False


@dataclass
class BrainSelection:
    role: str
    provider: str
    model: str
    agent_id: str
    reason: str
    fallback_used: bool
    supports_tools: bool | None = None
    supports_structured_outputs: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            "agent_id": self.agent_id,
            "reason": self.reason,
            "fallback_used": self.fallback_used,
            "supports_tools": self.supports_tools,
            "supports_structured_outputs": self.supports_structured_outputs,
        }


ROLE_PROFILES: dict[str, BrainProfile] = {
    "orchestrator": BrainProfile(
        role="orchestrator",
        purpose="planejamento executivo, decomposicao, decisao de rota e qualidade",
        openrouter_candidates=(
            "openrouter/free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "arcee-ai/trinity-large-preview:free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ),
        local_model=settings.LOCAL_MODEL_FALLBACK,
        temperature=0.15,
        require_structured=True,
    ),
    "planner": BrainProfile(
        role="planner",
        purpose="arquitetura, decomposicao tecnica e criterios de aceite",
        openrouter_candidates=(
            "qwen/qwen3-coder:free",
            "openai/gpt-oss-120b:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_FALLBACK,
        temperature=0.1,
    ),
    "frontend": BrainProfile(
        role="frontend",
        purpose="implementacao de UI, JS/TS, CSS, acessibilidade e build",
        openrouter_candidates=(
            "qwen/qwen3-coder:free",
            "openai/gpt-oss-120b:free",
            "minimax/minimax-m2.5:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_FALLBACK,
        temperature=0.08,
    ),
    "backend": BrainProfile(
        role="backend",
        purpose="APIs, automacao, filesystem, validacao e contratos de execucao",
        openrouter_candidates=(
            "qwen/qwen3-coder:free",
            "openai/gpt-oss-120b:free",
            "minimax/minimax-m2.5:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_FALLBACK,
        temperature=0.08,
    ),
    "qa": BrainProfile(
        role="qa",
        purpose="validacao, testes, regressao, build gates e criterio de aceite",
        openrouter_candidates=(
            "nvidia/nemotron-3-super-120b-a12b:free",
            "openai/gpt-oss-120b:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_VISION,
        temperature=0.05,
        require_structured=True,
    ),
    "security": BrainProfile(
        role="security",
        purpose="OWASP, hardening, secrets, permissao e risco operacional",
        openrouter_candidates=(
            "nvidia/nemotron-3-super-120b-a12b:free",
            "openai/gpt-oss-120b:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_VISION,
        temperature=0.05,
    ),
    "docs": BrainProfile(
        role="docs",
        purpose="documentacao tecnica, release notes, runbook e handoff",
        openrouter_candidates=(
            "google/gemma-4-31b-it:free",
            "openai/gpt-oss-20b:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_DOCS,
        temperature=0.15,
    ),
    "research": BrainProfile(
        role="research",
        purpose="pesquisa de mercado, concorrencia e contexto externo",
        openrouter_candidates=(
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "google/gemma-4-31b-it:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_FALLBACK,
        temperature=0.2,
    ),
    "strategy": BrainProfile(
        role="strategy",
        purpose="estrategia, posicionamento, roadmap e metricas",
        openrouter_candidates=(
            "google/gemma-4-31b-it:free",
            "arcee-ai/trinity-large-preview:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_FALLBACK,
        temperature=0.2,
    ),
    "content": BrainProfile(
        role="content",
        purpose="copy, narrativa, conteudo e iteracao criativa",
        openrouter_candidates=(
            "google/gemma-4-31b-it:free",
            "google/gemma-4-26b-a4b-it:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_FALLBACK,
        temperature=0.35,
        require_tools=False,
    ),
    "seo": BrainProfile(
        role="seo",
        purpose="SEO tecnico, semantica, pauta e otimizacao",
        openrouter_candidates=(
            "google/gemma-4-26b-a4b-it:free",
            "openai/gpt-oss-20b:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_FAST,
        temperature=0.2,
        require_tools=False,
    ),
    "social": BrainProfile(
        role="social",
        purpose="social media, calendario editorial e variacoes criativas",
        openrouter_candidates=(
            "google/gemma-4-26b-a4b-it:free",
            "openai/gpt-oss-20b:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_FAST,
        temperature=0.35,
        require_tools=False,
    ),
    "analytics": BrainProfile(
        role="analytics",
        purpose="metricas, gargalos, dashboards e analise de impacto",
        openrouter_candidates=(
            "nvidia/nemotron-3-super-120b-a12b:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "openrouter/free",
        ),
        local_model=settings.LOCAL_MODEL_VISION,
        temperature=0.05,
        require_structured=True,
    ),
}

_catalog_cache: dict[str, Any] = {"expires_at": 0.0, "models": {}}
_selection_log: list[BrainSelection] = []
_cloud_circuit: dict[str, Any] = {
    "openrouter_disabled_until": 0.0,
    "last_failure": "",
    "last_model": "",
}
# Per-model rate-limit tracking: model_id -> disabled_until (epoch seconds)
# Allows rotating to the next free candidate instead of killing all of OpenRouter.
_model_rate_limits: dict[str, float] = {}
_MODEL_RATE_LIMIT_COOLDOWN = 120  # seconds before retrying a rate-limited model


def get_brain_status() -> dict[str, Any]:
    return {
        "cloud_enabled": settings.BRAIN_CLOUD_ENABLED,
        "prefer_openrouter_free": settings.BRAIN_PREFER_OPENROUTER_FREE,
        "require_free_models": settings.BRAIN_REQUIRE_FREE_MODELS,
        "openrouter_key_configured": bool(_active_openrouter_key()),
        "catalog_cached_models": len(_catalog_cache.get("models") or {}),
        "cloud_circuit": _cloud_circuit_status(),
        "model_rate_limits": get_model_rate_limit_status(),
        "recent_selections": [item.to_dict() for item in _selection_log[-25:]],
        "profiles": {
            role: {
                "purpose": profile.purpose,
                "local_model": profile.local_model,
                "openrouter_candidates": list(profile.openrouter_candidates),
            }
            for role, profile in ROLE_PROFILES.items()
        },
    }


def get_profile(role: str) -> BrainProfile:
    return ROLE_PROFILES.get(role, ROLE_PROFILES["orchestrator"])


def get_langchain_llm_for_role(role: str, agent_id: str, temperature: float | None = None) -> BaseChatModel:
    profile = get_profile(role)
    selection = select_brain(role=role, agent_id=agent_id)
    temp = profile.temperature if temperature is None else temperature
    if selection.provider == "openrouter":
        return ChatOpenAI(
            model=selection.model,
            openai_api_key=_active_openrouter_key(),
            openai_api_base=OPENROUTER_BASE_URL,
            temperature=temp,
            max_tokens=profile.max_tokens,
            default_headers={
                "HTTP-Referer": "https://ai-office-system.local",
                "X-Title": "IRIS AI Office System",
            },
        )
    return ChatOllama(
        model=selection.model,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=temp,
        num_predict=profile.max_tokens,
    )


def get_crewai_llm_for_role(role: str, agent_id: str) -> str | LLM:
    profile = get_profile(role)
    selection = select_brain(role=role, agent_id=agent_id)
    if selection.provider == "openrouter":
        return LLM(
            model=f"openrouter/{selection.model}",
            api_key=_active_openrouter_key(),
            base_url=OPENROUTER_BASE_URL,
            temperature=profile.temperature,
            max_tokens=profile.max_tokens,
            timeout=settings.SUBTASK_EXECUTION_TIMEOUT_SECONDS,
        )
    return f"ollama/{selection.model}"


def select_brain(role: str, agent_id: str = "unknown") -> BrainSelection:
    profile = get_profile(role)
    if (
        settings.BRAIN_CLOUD_ENABLED
        and settings.BRAIN_PREFER_OPENROUTER_FREE
        and _active_openrouter_key()
        and not _is_openrouter_circuit_open()
    ):
        model = _select_openrouter_free_model(profile)
        if model:
            gate.validate(model["id"], agent_id=agent_id)
            selection = BrainSelection(
                role=role,
                provider="openrouter",
                model=model["id"],
                agent_id=agent_id,
                reason=f"free OpenRouter model for {profile.purpose}",
                fallback_used=False,
                supports_tools=model.get("tools"),
                supports_structured_outputs=model.get("structured_outputs"),
            )
            _record_selection(selection)
            return selection

    selection = BrainSelection(
        role=role,
        provider="ollama",
        model=profile.local_model,
        agent_id=agent_id,
        reason="local fallback: OpenRouter disabled, no key, or no matching free model",
        fallback_used=True,
    )
    _record_selection(selection)
    return selection


def record_transient_openrouter_failure(model: str, error: Exception | str) -> None:
    """Per-model rate-limit isolation.

    429 / quota errors: marca APENAS o modelo que falhou com cooldown curto (120s).
    Outros candidatos do mesmo role continuam disponíveis sem interrupção.

    Falhas de auth / rede: abre o circuito global para evitar spam de erros.
    """
    model_id = _normalize_openrouter_model_id(model)
    err_str = _sanitize_failure(str(error))
    is_rate_limit = any(
        token in err_str.lower()
        for token in ("429", "rate limit", "rate_limit", "quota", "too many request")
    )

    if is_rate_limit:
        _model_rate_limits[model_id] = time.time() + _MODEL_RATE_LIMIT_COOLDOWN
        logger.warning(
            "[BrainRouter] %s rate-limited — bloqueado por %ss, proximos candidatos livres.",
            model_id or "unknown",
            _MODEL_RATE_LIMIT_COOLDOWN,
        )
    else:
        cooldown_seconds = max(30, int(settings.OPENROUTER_TRANSIENT_COOLDOWN_SECONDS or 300))
        _cloud_circuit["openrouter_disabled_until"] = time.time() + cooldown_seconds
        _cloud_circuit["last_model"] = model_id
        _cloud_circuit["last_failure"] = err_str
        logger.warning(
            "[BrainRouter] Falha nao-RateLimit em %s — circuito global aberto por %ss.",
            model_id or "unknown",
            cooldown_seconds,
        )


def _is_openrouter_circuit_open() -> bool:
    return time.time() < float(_cloud_circuit.get("openrouter_disabled_until") or 0)


def _cloud_circuit_status() -> dict[str, Any]:
    disabled_until = float(_cloud_circuit.get("openrouter_disabled_until") or 0)
    now = time.time()
    return {
        "openrouter_circuit_open": now < disabled_until,
        "cooldown_remaining_seconds": max(0, int(disabled_until - now)),
        "last_model": _cloud_circuit.get("last_model") or "",
        "last_failure": _cloud_circuit.get("last_failure") or "",
    }


def _normalize_openrouter_model_id(value: str) -> str:
    raw = str(value or "").strip()
    match = re.search(r"openrouter/([A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+)", raw)
    if match:
        return match.group(1)
    match = re.search(r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+:free)", raw)
    if match:
        return match.group(1)
    return raw or "unknown"


def _sanitize_failure(value: str) -> str:
    return value.replace("\n", " ")[:320]


def _record_selection(selection: BrainSelection) -> None:
    _selection_log.append(selection)
    if len(_selection_log) > 200:
        del _selection_log[:-200]
    logger.info(
        "[BrainRouter] %s/%s -> %s:%s (%s)",
        selection.role,
        selection.agent_id,
        selection.provider,
        selection.model,
        selection.reason,
    )


def _active_openrouter_key() -> str:
    return settings.OPENROUTER_API_KEY.strip()


def _select_openrouter_free_model(profile: BrainProfile) -> dict[str, Any] | None:
    catalog = _get_openrouter_catalog()
    now = time.time()
    for candidate in profile.openrouter_candidates:
        model = catalog.get(candidate)
        if not model:
            continue
        # Skip models that hit their individual rate-limit cooldown
        if now < float(_model_rate_limits.get(model["id"]) or 0):
            logger.debug("[BrainRouter] %s ainda em cooldown (%.0fs), pulando.", model["id"],
                         _model_rate_limits[model["id"]] - now)
            continue
        if profile.require_tools and not model.get("tools"):
            continue
        if profile.require_structured and not model.get("structured_outputs"):
            continue
        return model
    # Last resort generic free slot — skip if rate-limited too
    fallback = catalog.get("openrouter/free")
    if fallback and now >= float(_model_rate_limits.get(fallback["id"]) or 0):
        return fallback
    return None


def get_model_rate_limit_status() -> dict[str, int]:
    """Returns per-model remaining cooldown in seconds (only models still cooling down)."""
    now = time.time()
    return {mid: int(until - now) for mid, until in _model_rate_limits.items() if until > now}


def _get_openrouter_catalog() -> dict[str, dict[str, Any]]:
    now = time.time()
    if now < float(_catalog_cache.get("expires_at") or 0):
        return _catalog_cache["models"]

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{OPENROUTER_BASE_URL}/models")
            response.raise_for_status()
            rows = response.json().get("data", [])
    except Exception as exc:
        logger.warning("[BrainRouter] OpenRouter catalog unavailable: %s", exc)
        return _catalog_cache.get("models") or {}

    models: dict[str, dict[str, Any]] = {}
    for item in rows:
        model_id = item.get("id")
        if not model_id or not _is_free_model(item):
            continue
        supported = item.get("supported_parameters") or []
        models[model_id] = {
            "id": model_id,
            "name": item.get("name") or model_id,
            "context_length": item.get("context_length"),
            "tools": "tools" in supported,
            "structured_outputs": "structured_outputs" in supported,
            "response_format": "response_format" in supported,
        }

    _catalog_cache["models"] = models
    _catalog_cache["expires_at"] = now + settings.OPENROUTER_MODEL_CATALOG_TTL_SECONDS
    return models


def _is_free_model(item: dict[str, Any]) -> bool:
    model_id = str(item.get("id") or "")
    if model_id == "openrouter/free" or model_id.endswith(":free"):
        return True
    pricing = item.get("pricing") or {}
    return all(str(pricing.get(key, "0")) in {"0", "0.0"} for key in ("prompt", "completion", "request"))
