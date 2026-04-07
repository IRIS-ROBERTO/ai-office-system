"""
AI Office System — Model Gate
Camada de segurança que impede uso de modelos caros via OpenRouter.

Regras inegociáveis:
  1. Apenas modelos da APPROVED_MODELS podem ser usados
  2. Modelos com sufixo :free têm custo zero — sempre permitidos
  3. Modelos pagos só passam se custo estimado < COST_LIMIT_PER_CALL_USD
  4. Qualquer tentativa de usar modelo não aprovado levanta ModelNotAllowedError
  5. Todo uso é registrado no log para auditoria

Atualizar APPROVED_MODELS requer alteração explícita aqui — nunca via .env.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Whitelist de modelos aprovados
# Custo em USD por 1 token (prompt / completion)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ApprovedModel:
    model_id: str
    display_name: str
    prompt_cost_per_token: float       # USD por token de entrada
    completion_cost_per_token: float   # USD por token de saída
    context_length: int
    best_for: str                      # documentação de uso

# Modelos 100% gratuitos — custo zero garantido pelo OpenRouter
FREE_MODELS: list[ApprovedModel] = [
    ApprovedModel(
        model_id="qwen/qwen3-coder:free",
        display_name="Qwen3 Coder (Free)",
        prompt_cost_per_token=0.0,
        completion_cost_per_token=0.0,
        context_length=262_000,
        best_for="Código — melhor modelo gratuito para dev team",
    ),
    ApprovedModel(
        model_id="meta-llama/llama-3.3-70b-instruct:free",
        display_name="Llama 3.3 70B (Free)",
        prompt_cost_per_token=0.0,
        completion_cost_per_token=0.0,
        context_length=65_536,
        best_for="Senior orchestrator, planejamento, análise geral",
    ),
    ApprovedModel(
        model_id="nvidia/nemotron-3-super-120b-a12b:free",
        display_name="Nemotron 120B Super (Free)",
        prompt_cost_per_token=0.0,
        completion_cost_per_token=0.0,
        context_length=262_144,
        best_for="Quality gate — modelo grande para validação crítica",
    ),
    ApprovedModel(
        model_id="google/gemma-4-31b-it:free",
        display_name="Gemma 4 31B (Free)",
        prompt_cost_per_token=0.0,
        completion_cost_per_token=0.0,
        context_length=262_144,
        best_for="Marketing team — conteúdo e estratégia",
    ),
    ApprovedModel(
        model_id="qwen/qwen3.6-plus:free",
        display_name="Qwen 3.6 Plus (Free) — 1M ctx",
        prompt_cost_per_token=0.0,
        completion_cost_per_token=0.0,
        context_length=1_000_000,
        best_for="Tarefas com contexto muito longo (análise de codebase inteira)",
    ),
    ApprovedModel(
        model_id="qwen/qwen3-next-80b-a3b-instruct:free",
        display_name="Qwen3 80B MoE (Free)",
        prompt_cost_per_token=0.0,
        completion_cost_per_token=0.0,
        context_length=262_144,
        best_for="Research e analytics — raciocínio complexo",
    ),
    ApprovedModel(
        model_id="google/gemma-4-26b-a4b-it:free",
        display_name="Gemma 4 26B MoE (Free)",
        prompt_cost_per_token=0.0,
        completion_cost_per_token=0.0,
        context_length=262_144,
        best_for="SEO, social — tarefas leves e rápidas",
    ),
    ApprovedModel(
        model_id="nousresearch/hermes-3-llama-3.1-405b:free",
        display_name="Hermes 3 405B (Free)",
        prompt_cost_per_token=0.0,
        completion_cost_per_token=0.0,
        context_length=131_072,
        best_for="Fallback premium — 405B gratuito para tarefas críticas",
    ),
    ApprovedModel(
        model_id="openrouter/free",
        display_name="OpenRouter Auto (Free)",
        prompt_cost_per_token=0.0,
        completion_cost_per_token=0.0,
        context_length=200_000,
        best_for="Roteamento automático entre modelos gratuitos",
    ),
]

# Modelos pagos com custo muito baixo (aprovados com limite por chamada)
CHEAP_MODELS: list[ApprovedModel] = [
    ApprovedModel(
        model_id="meta-llama/llama-3.1-8b-instruct",
        display_name="Llama 3.1 8B",
        prompt_cost_per_token=0.02 / 1_000_000,
        completion_cost_per_token=0.05 / 1_000_000,
        context_length=131_072,
        best_for="Fallback pago baratíssimo — $0.02/1M tokens",
    ),
    ApprovedModel(
        model_id="mistralai/mistral-nemo",
        display_name="Mistral Nemo 12B",
        prompt_cost_per_token=0.02 / 1_000_000,
        completion_cost_per_token=0.04 / 1_000_000,
        context_length=128_000,
        best_for="Tarefas rápidas com fallback pago",
    ),
]

# Índice rápido: model_id → ApprovedModel
APPROVED_MODELS: dict[str, ApprovedModel] = {
    m.model_id: m for m in (FREE_MODELS + CHEAP_MODELS)
}

# ─────────────────────────────────────────────────────────────────────────────
# Limite de custo por chamada (para modelos pagos)
# ─────────────────────────────────────────────────────────────────────────────
COST_LIMIT_PER_CALL_USD: float = 0.005   # máximo $0.005 por chamada (~250 tokens a $0.02/1M)
DAILY_BUDGET_USD: float = 0.10           # máximo $0.10/dia em modelos pagos

# ─────────────────────────────────────────────────────────────────────────────
# Registro de uso (in-memory, substituível por Supabase em produção)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class UsageRecord:
    model_id: str
    estimated_cost_usd: float
    timestamp: str
    agent_id: str
    approved: bool

_usage_log: list[UsageRecord] = []
_daily_spend_usd: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Exceções
# ─────────────────────────────────────────────────────────────────────────────

class ModelNotAllowedError(Exception):
    """Levantada quando um agente tenta usar modelo fora da whitelist."""
    pass

class BudgetExceededError(Exception):
    """Levantada quando o custo estimado ultrapassa o limite configurado."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Gate principal
# ─────────────────────────────────────────────────────────────────────────────

class ModelGate:
    """
    Valida e autoriza uso de modelos OpenRouter.
    Deve ser chamado antes de qualquer invocação de LLM externo.
    """

    @staticmethod
    def validate(model_id: str, agent_id: str = "unknown",
                 estimated_input_tokens: int = 1000,
                 estimated_output_tokens: int = 500) -> ApprovedModel:
        """
        Valida se o modelo pode ser usado. Levanta exceção se não puder.

        Args:
            model_id: ID do modelo OpenRouter (ex: 'qwen/qwen3-coder:free')
            agent_id: Identificador do agente para logging
            estimated_input_tokens: Estimativa de tokens de entrada
            estimated_output_tokens: Estimativa de tokens de saída

        Returns:
            ApprovedModel com metadata do modelo aprovado

        Raises:
            ModelNotAllowedError: modelo não está na whitelist
            BudgetExceededError: custo estimado ultrapassa o limite
        """
        global _daily_spend_usd

        # 1. Verifica whitelist
        approved = APPROVED_MODELS.get(model_id)
        if not approved:
            logger.error(
                "[ModelGate] BLOQUEADO — modelo '%s' nao esta na whitelist. "
                "Agente: %s. Adicione explicitamente em model_gate.py se necessario.",
                model_id, agent_id
            )
            raise ModelNotAllowedError(
                f"Modelo '{model_id}' nao autorizado. "
                f"Use apenas: {list(APPROVED_MODELS.keys())}"
            )

        # 2. Estimativa de custo
        cost = (
            approved.prompt_cost_per_token * estimated_input_tokens +
            approved.completion_cost_per_token * estimated_output_tokens
        )

        # 3. Verifica limite por chamada (apenas modelos pagos)
        if cost > 0 and cost > COST_LIMIT_PER_CALL_USD:
            raise BudgetExceededError(
                f"Custo estimado ${cost:.6f} ultrapassa limite por chamada "
                f"${COST_LIMIT_PER_CALL_USD:.3f} para modelo '{model_id}'"
            )

        # 4. Verifica orçamento diário
        if _daily_spend_usd + cost > DAILY_BUDGET_USD:
            raise BudgetExceededError(
                f"Orcamento diario de ${DAILY_BUDGET_USD:.2f} seria ultrapassado. "
                f"Gasto atual: ${_daily_spend_usd:.4f}"
            )

        # 5. Registra uso
        _daily_spend_usd += cost
        record = UsageRecord(
            model_id=model_id,
            estimated_cost_usd=cost,
            timestamp=datetime.utcnow().isoformat(),
            agent_id=agent_id,
            approved=True,
        )
        _usage_log.append(record)

        if cost == 0:
            logger.info("[ModelGate] APROVADO (gratis) — %s para agente %s", model_id, agent_id)
        else:
            logger.info(
                "[ModelGate] APROVADO — %s | custo estimado $%.6f | gasto diario $%.4f",
                model_id, cost, _daily_spend_usd
            )

        return approved

    @staticmethod
    def get_usage_summary() -> dict:
        """Retorna resumo de uso para o endpoint /health."""
        free_calls = sum(1 for r in _usage_log if r.estimated_cost_usd == 0)
        paid_calls = sum(1 for r in _usage_log if r.estimated_cost_usd > 0)
        return {
            "total_calls": len(_usage_log),
            "free_calls": free_calls,
            "paid_calls": paid_calls,
            "daily_spend_usd": round(_daily_spend_usd, 6),
            "daily_budget_usd": DAILY_BUDGET_USD,
            "budget_remaining_usd": round(DAILY_BUDGET_USD - _daily_spend_usd, 6),
        }

    @staticmethod
    def list_approved() -> list[dict]:
        """Lista modelos aprovados — útil para o endpoint /models."""
        return [
            {
                "model_id": m.model_id,
                "display_name": m.display_name,
                "free": m.prompt_cost_per_token == 0,
                "context_length": m.context_length,
                "best_for": m.best_for,
            }
            for m in APPROVED_MODELS.values()
        ]


# Instância global
gate = ModelGate()
