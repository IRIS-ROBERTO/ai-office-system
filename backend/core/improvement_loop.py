"""
Improvement Loop — o coração do sistema reflexivo.

Fluxo após cada tarefa completada:
  1. Cada agente escreve uma CriticalAnalysis do que fez
  2. ImprovementSynthesizer agrega as análises
  3. Orchestrator prioriza e apresenta ImprovementProposals ao usuário
  4. Usuário aprova/rejeita cada proposta via API
  5. Propostas aprovadas viram novas tarefas na próxima sprint

Princípio: o sistema fica mais inteligente a cada interação.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from backend.config.settings import settings
from backend.core.event_bus import event_bus
from backend.core.event_types import AgentRole, EventType, OfficialEvent, TeamType
from backend.core.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CriticalAnalysis:
    """
    Auto-análise crítica produzida por um agente ao concluir uma tarefa.
    Captura aprendizado real — não relatório de status.
    """

    agent_id: str
    agent_role: str
    task_id: str
    what_worked: str            # O que funcionou bem — ser específico
    what_failed: str            # O que não funcionou — sem desculpas
    bottleneck: str             # Onde perdeu mais tempo/tokens
    improvement_suggestion: str # Proposta concreta e acionável
    confidence: float           # 0.0 a 1.0 — confiança na sugestão
    category: str               # "performance" | "quality" | "architecture" | "tooling"
    estimated_impact: str       # "low" | "medium" | "high"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "task_id": self.task_id,
            "what_worked": self.what_worked,
            "what_failed": self.what_failed,
            "bottleneck": self.bottleneck,
            "improvement_suggestion": self.improvement_suggestion,
            "confidence": self.confidence,
            "category": self.category,
            "estimated_impact": self.estimated_impact,
            "timestamp": self.timestamp,
        }


@dataclass
class ImprovementProposal:
    """
    Proposta consolidada de melhoria para aprovação do usuário.
    Agrega análises convergentes de múltiplos agentes.
    """

    proposal_id: str
    title: str                      # Título curto (< 60 chars)
    description: str                # Descrição detalhada do que mudar e por quê
    category: str                   # "performance" | "quality" | "architecture" | "tooling"
    estimated_impact: str           # "low" | "medium" | "high"
    estimated_effort: str           # "1h" | "1d" | "1week"
    supporting_analyses: list[str]  # agent_ids que identificaram o problema
    status: str                     # "pending" | "approved" | "rejected" | "implemented"
    created_at: str
    votes: int                      # quantos agentes identificaram o mesmo problema
    community_reference: str        # link ou nome de best practice da comunidade

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "estimated_impact": self.estimated_impact,
            "estimated_effort": self.estimated_effort,
            "supporting_analyses": self.supporting_analyses,
            "status": self.status,
            "created_at": self.created_at,
            "votes": self.votes,
            "community_reference": self.community_reference,
        }


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SELF_ANALYSIS_SYSTEM = """Você é um agente de IA altamente especializado que acabou de completar uma tarefa.
Sua missão agora é a mais difícil: analisar sua própria performance com honestidade brutal.

REGRAS ABSOLUTAS:
- ZERO auto-elogio vazio. "Funcionou bem" só é válido se explicar EXATAMENTE por quê.
- Identifique falhas REAIS — não generalize com "poderia melhorar". Seja específico.
- Se não houve falha nenhuma, você provavelmente não está olhando com cuidado suficiente.
- O bottleneck deve ser o gargalo REAL — onde o tempo/tokens foram desperdiçados.
- A improvement_suggestion deve ser algo que pode ser IMPLEMENTADO na próxima sprint.
- confidence reflete o quanto você tem certeza que a sugestão realmente resolveria o problema.

CATEGORIAS VÁLIDAS:
  performance  — velocidade, uso de tokens, latência
  quality      — precisão, cobertura, profundidade do output
  architecture — estrutura do prompt, fluxo entre agentes, handoffs
  tooling      — ferramentas, APIs, integrações

IMPACTOS:
  high   — resolveria problema frequente ou crítico
  medium — melhoria notável mas não urgente
  low    — refinamento cosmético ou marginal

Responda SOMENTE com JSON válido, sem markdown, sem texto antes ou depois."""

_SELF_ANALYSIS_TEMPLATE = """Agente: {agent_role} (ID: {agent_id})
Tarefa concluída: {task_id}

OUTPUT QUE VOCÊ PRODUZIU:
---
{task_output}
---

Analise sua performance nesta tarefa com honestidade brutal.

Responda com este JSON exato (todos os campos obrigatórios):
{{
  "what_worked": "<o que funcionou bem — seja específico, cite o que no output prova isso>",
  "what_failed": "<o que não funcionou ou foi subótimo — seja brutal e específico>",
  "bottleneck": "<onde você perdeu mais tempo ou tokens — qual etapa ou decisão custou mais>",
  "improvement_suggestion": "<proposta concreta e acionável — o que exatamente mudar no sistema>",
  "confidence": <float entre 0.0 e 1.0 — quão certo você está que a sugestão funciona>,
  "category": "<performance|quality|architecture|tooling>",
  "estimated_impact": "<low|medium|high>"
}}"""

_SYNTHESIS_SYSTEM = """Você é um Arquiteto Sênior de Sistemas de IA com profundo conhecimento de:
- LangGraph (grafos de agentes, state machines, checkpointing)
- CrewAI (crews, roles, task delegation, memory)
- LangChain (chains, prompts, output parsers, tools)
- Engenharia de prompts de alta performance
- Sistemas multi-agente em produção

Sua tarefa: agregar análises críticas de múltiplos agentes em propostas de melhoria acionáveis.

PRINCÍPIOS DE SÍNTESE:
1. Análises CONVERGENTES (múltiplos agentes identificando o mesmo problema) = alta prioridade
2. Cada proposta deve ter título CLARO (< 60 chars) e descrição técnica detalhada
3. Esforço realista: "1h" para mudança de prompt, "1d" para refactoring de agente, "1week" para arquitetura
4. community_reference: cite documentação, padrão ou discussão da comunidade relevante
   Exemplos: "LangGraph Persistence Docs", "CrewAI Memory System", "ReAct Paper (Yao et al.)",
             "OpenAI Prompt Engineering Guide", "Anthropic Constitutional AI"
5. Consolide análises similares em UMA proposta com votes = N agentes que identificaram

Retorne SOMENTE JSON válido — array de proposals, sem markdown."""

_SYNTHESIS_TEMPLATE = """ANÁLISES RECEBIDAS DE {n_agents} AGENTES:

{analyses_json}

Sintetize estas análises em propostas de melhoria.
Consolide problemas similares (mesmo bottleneck/categoria) em uma única proposta.
Ordene por: votes DESC, estimated_impact (high > medium > low).

Retorne um array JSON com este schema por item:
{{
  "title": "<título conciso, < 60 chars>",
  "description": "<descrição técnica: o que mudar, como mudar, por que vai funcionar>",
  "category": "<performance|quality|architecture|tooling>",
  "estimated_impact": "<low|medium|high>",
  "estimated_effort": "<1h|1d|1week>",
  "supporting_agents": ["<agent_id_1>", "<agent_id_2>"],
  "votes": <int — quantos agentes identificaram>,
  "community_reference": "<nome ou link de best practice relevante>"
}}"""


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------


class ImprovementLoop:
    """
    Orquestra o ciclo reflexivo de melhoria contínua.

    Após cada tarefa completada:
      collect_agent_analysis()  — agente analisa sua própria performance
      synthesize_proposals()    — sênior agrega análises em proposals
      present_to_user()         — formata para aprovação humana
      process_approval()        — persiste decisão e emite evento
    """

    def __init__(self) -> None:
        self._pending_proposals: list[ImprovementProposal] = []
        self._client = None

    async def _get_client(self):
        if self._client is None:
            self._client = await get_supabase_client()
        return self._client

    # ------------------------------------------------------------------
    # 1. Coleta de análise de cada agente
    # ------------------------------------------------------------------

    async def collect_agent_analysis(
        self,
        agent_id: str,
        agent_role: str,
        task_id: str,
        task_output: str,
        llm: BaseChatModel,
    ) -> CriticalAnalysis:
        """
        Usa o próprio LLM do agente para auto-análise crítica.

        O agente que executou a tarefa é o mais qualificado para identificar
        onde gastou tokens desnecessariamente, onde o prompt foi ambíguo,
        e o que poderia ter feito diferente.

        Args:
            agent_id    : Identificador único do agente.
            agent_role  : Role do agente (ex.: "backend", "qa").
            task_id     : UUID da tarefa concluída.
            task_output : Output completo que o agente produziu.
            llm         : Instância do LLM do agente (BaseChatModel).

        Returns:
            CriticalAnalysis com a auto-avaliação parseada.

        Raises:
            ValueError : Se o LLM retornar JSON inválido ou campos ausentes.
        """
        logger.info(
            "[ImprovementLoop] Coletando análise do agente %s para tarefa %s",
            agent_id,
            task_id,
        )

        prompt_user = _SELF_ANALYSIS_TEMPLATE.format(
            agent_role=agent_role,
            agent_id=agent_id,
            task_id=task_id,
            task_output=task_output[:6000],  # limita para não explodir o contexto
        )

        messages = [
            SystemMessage(content=_SELF_ANALYSIS_SYSTEM),
            HumanMessage(content=prompt_user),
        ]

        try:
            response = await llm.ainvoke(messages)
            raw = response.content.strip()

            # Remove possíveis marcadores de código que modelos insistem em usar
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(
                "[ImprovementLoop] JSON inválido do agente %s: %s | raw=%r",
                agent_id,
                exc,
                raw[:300],
            )
            # Análise fallback — não interrompe o fluxo
            parsed = {
                "what_worked": "Output entregue dentro do escopo solicitado.",
                "what_failed": "Análise automática falhou — revisar manualmente.",
                "bottleneck": "Parse da auto-análise (JSON malformado pelo LLM).",
                "improvement_suggestion": "Ajustar prompt de análise para forçar JSON puro.",
                "confidence": 0.3,
                "category": "tooling",
                "estimated_impact": "medium",
            }

        analysis = CriticalAnalysis(
            agent_id=agent_id,
            agent_role=agent_role,
            task_id=task_id,
            what_worked=str(parsed.get("what_worked", "")),
            what_failed=str(parsed.get("what_failed", "")),
            bottleneck=str(parsed.get("bottleneck", "")),
            improvement_suggestion=str(parsed.get("improvement_suggestion", "")),
            confidence=float(parsed.get("confidence", 0.5)),
            category=str(parsed.get("category", "quality")),
            estimated_impact=str(parsed.get("estimated_impact", "medium")),
        )

        logger.info(
            "[ImprovementLoop] Análise coletada: agent=%s category=%s impact=%s confidence=%.2f",
            agent_id,
            analysis.category,
            analysis.estimated_impact,
            analysis.confidence,
        )
        return analysis

    # ------------------------------------------------------------------
    # 2. Síntese de proposals (Senior LLM)
    # ------------------------------------------------------------------

    async def synthesize_proposals(
        self,
        analyses: list[CriticalAnalysis],
        senior_llm: BaseChatModel,
    ) -> list[ImprovementProposal]:
        """
        Usa o LLM sênior para agregar análises convergentes em proposals.

        Análises do mesmo problema identificadas por múltiplos agentes ganham
        mais votes e portanto aparecem primeiro para o usuário. O LLM sênior
        tem visão global e referencia best practices da comunidade.

        Args:
            analyses   : Lista de CriticalAnalysis coletadas nesta sprint.
            senior_llm : LLM de maior capacidade (ex.: Gemini 2.0 Flash).

        Returns:
            Lista de ImprovementProposal ordenada por relevância.
        """
        if not analyses:
            logger.warning("[ImprovementLoop] Nenhuma análise para sintetizar.")
            return []

        logger.info(
            "[ImprovementLoop] Sintetizando %d análises em proposals...", len(analyses)
        )

        analyses_json = json.dumps(
            [a.to_dict() for a in analyses],
            ensure_ascii=False,
            indent=2,
        )

        prompt_user = _SYNTHESIS_TEMPLATE.format(
            n_agents=len(analyses),
            analyses_json=analyses_json,
        )

        messages = [
            SystemMessage(content=_SYNTHESIS_SYSTEM),
            HumanMessage(content=prompt_user),
        ]

        try:
            response = await senior_llm.ainvoke(messages)
            raw = response.content.strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            proposals_raw: list[dict] = json.loads(raw)
            if not isinstance(proposals_raw, list):
                proposals_raw = [proposals_raw]

        except (json.JSONDecodeError, Exception) as exc:
            logger.error(
                "[ImprovementLoop] Falha ao sintetizar proposals: %s", exc, exc_info=True
            )
            return []

        now = datetime.now(timezone.utc).isoformat()
        proposals: list[ImprovementProposal] = []

        for p in proposals_raw:
            proposal = ImprovementProposal(
                proposal_id=str(uuid.uuid4()),
                title=str(p.get("title", "Melhoria sem título"))[:60],
                description=str(p.get("description", "")),
                category=str(p.get("category", "quality")),
                estimated_impact=str(p.get("estimated_impact", "medium")),
                estimated_effort=str(p.get("estimated_effort", "1d")),
                supporting_analyses=list(p.get("supporting_agents", [])),
                status="pending",
                created_at=now,
                votes=int(p.get("votes", 1)),
                community_reference=str(p.get("community_reference", "")),
            )
            proposals.append(proposal)

        # Ordena: votes DESC, depois impact (high > medium > low)
        _impact_order = {"high": 3, "medium": 2, "low": 1}
        proposals.sort(
            key=lambda p: (p.votes, _impact_order.get(p.estimated_impact, 0)),
            reverse=True,
        )

        # Atualiza estado interno
        self._pending_proposals.extend(proposals)

        logger.info(
            "[ImprovementLoop] %d proposals sintetizadas.", len(proposals)
        )
        return proposals

    # ------------------------------------------------------------------
    # 3. Apresentação ao usuário
    # ------------------------------------------------------------------

    async def present_to_user(
        self,
        proposals: list[ImprovementProposal],
    ) -> str:
        """
        Formata proposals em markdown legível para exibição ao usuário.

        Inclui: título, impacto, esforço, referência da comunidade, agentes
        que identificaram o problema e o botão de aprovação/rejeição.

        Args:
            proposals : Lista de ImprovementProposal a apresentar.

        Returns:
            String markdown formatada para o frontend.
        """
        if not proposals:
            return "Nenhuma proposta de melhoria pendente nesta sprint."

        _impact_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        _effort_label = {"1h": "1 hora", "1d": "1 dia", "1week": "1 semana"}
        _category_label = {
            "performance": "Performance",
            "quality": "Qualidade",
            "architecture": "Arquitetura",
            "tooling": "Ferramentas",
        }

        lines = [
            "# Propostas de Melhoria — Sprint Review",
            "",
            f"> {len(proposals)} proposta(s) identificada(s) pelos agentes nesta sprint.",
            "",
        ]

        for i, p in enumerate(proposals, start=1):
            impact_icon = _impact_emoji.get(p.estimated_impact, "⚪")
            effort_label = _effort_label.get(p.estimated_effort, p.estimated_effort)
            cat_label = _category_label.get(p.category, p.category.title())
            agents_str = ", ".join(p.supporting_analyses) if p.supporting_analyses else "—"
            votes_label = f"{p.votes} agente(s)"

            lines += [
                f"## {i}. {p.title}",
                "",
                f"**Categoria:** {cat_label}  ",
                f"**Impacto:** {impact_icon} {p.estimated_impact.upper()}  ",
                f"**Esforço estimado:** {effort_label}  ",
                f"**Votos:** {votes_label}  ",
                f"**Referência da comunidade:** {p.community_reference or '—'}  ",
                f"**Agentes:** {agents_str}",
                "",
                "**Descrição:**",
                p.description,
                "",
                f"| ✅ Aprovar | ❌ Rejeitar |",
                f"|-----------|------------|",
                f"| `POST /api/improvements/{p.proposal_id}/approve` | `POST /api/improvements/{p.proposal_id}/reject` |",
                "",
                "---",
                "",
            ]

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 4. Processamento de aprovação/rejeição
    # ------------------------------------------------------------------

    async def process_approval(
        self,
        proposal_id: str,
        approved: bool,
        user_comment: str = "",
    ) -> None:
        """
        Registra a decisão do usuário sobre uma proposal.

        Se aprovada: atualiza status no Supabase, cria tarefa de melhoria
        no sistema e emite evento via EventBus.

        Se rejeitada: registra rejeição com comentário para aprendizado futuro.

        Args:
            proposal_id  : UUID da proposal a decidir.
            approved     : True = aprovada, False = rejeitada.
            user_comment : Comentário opcional do usuário.
        """
        new_status = "approved" if approved else "rejected"
        now = datetime.now(timezone.utc).isoformat()

        # Atualiza estado in-memory
        proposal = self._find_pending_proposal(proposal_id)
        if proposal:
            proposal.status = new_status

        # Persiste no Supabase
        try:
            client = await self._get_client()
            client.table("improvement_proposals").update(
                {
                    "status": new_status,
                    "user_comment": user_comment,
                    "decided_at": now,
                }
            ).eq("proposal_id", proposal_id).execute()

            logger.info(
                "[ImprovementLoop] Proposal %s marcada como %s.",
                proposal_id,
                new_status,
            )
        except Exception as exc:
            logger.error(
                "[ImprovementLoop] Falha ao atualizar proposal %s no Supabase: %s",
                proposal_id,
                exc,
                exc_info=True,
            )

        # Emite evento via EventBus
        event = OfficialEvent(
            event_type=EventType.TASK_CREATED if approved else EventType.TASK_FAILED,
            team=TeamType.DEV,
            agent_id="improvement_loop",
            agent_role=AgentRole.ORCHESTRATOR,
            task_id=proposal_id,
            payload={
                "action": "improvement_proposal_decision",
                "proposal_id": proposal_id,
                "status": new_status,
                "user_comment": user_comment,
                "proposal_title": proposal.title if proposal else "",
            },
        )

        try:
            await event_bus.emit(event)
        except Exception as exc:
            logger.warning(
                "[ImprovementLoop] Falha ao emitir evento de decisão: %s", exc
            )

        # Se aprovada, cria tarefa de melhoria
        if approved and proposal:
            await self._create_improvement_task(proposal, user_comment)

    async def _create_improvement_task(
        self,
        proposal: ImprovementProposal,
        user_comment: str,
    ) -> None:
        """
        Transforma uma proposal aprovada em tarefa concreta no sistema.

        A tarefa é inserida na tabela `tasks` com status 'queued' e
        request descrevendo o que deve ser implementado.
        """
        try:
            client = await self._get_client()
            task_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()

            request_text = (
                f"[IMPROVEMENT] {proposal.title}\n\n"
                f"{proposal.description}\n\n"
                f"Esforço estimado: {proposal.estimated_effort} | "
                f"Impacto: {proposal.estimated_impact}\n"
                f"Referência: {proposal.community_reference}\n"
                f"Comentário do usuário: {user_comment}"
            )

            row = {
                "task_id": task_id,
                "team": "dev",
                "status": "queued",
                "request": request_text,
                "senior_directive": (
                    f"Implementar melhoria aprovada: {proposal.title}. "
                    f"Categoria: {proposal.category}. "
                    f"Referência: {proposal.community_reference}."
                ),
                "subtasks": [],
                "agent_outputs": {},
                "final_output": None,
                "error_count": 0,
                "retry_count": 0,
                "created_at": now,
                "updated_at": now,
            }

            client.table("tasks").insert(row).execute()

            logger.info(
                "[ImprovementLoop] Tarefa de melhoria criada: task_id=%s title=%s",
                task_id,
                proposal.title,
            )
        except Exception as exc:
            logger.error(
                "[ImprovementLoop] Falha ao criar tarefa de melhoria: %s", exc, exc_info=True
            )

    # ------------------------------------------------------------------
    # 5. Persistência no Supabase
    # ------------------------------------------------------------------

    async def save_to_supabase(
        self,
        analyses: list[CriticalAnalysis],
        proposals: list[ImprovementProposal],
    ) -> None:
        """
        Persiste análises e proposals para histórico e aprendizado futuro.

        Dados persistidos alimentam dashboards de qualidade e permitem
        identificar padrões de melhoria ao longo do tempo.

        Args:
            analyses  : Lista de CriticalAnalysis da sprint atual.
            proposals : Lista de ImprovementProposal sintetizadas.
        """
        try:
            client = await self._get_client()

            # Salva análises
            if analyses:
                analysis_rows = [
                    {
                        "agent_id": a.agent_id,
                        "agent_role": a.agent_role,
                        "task_id": a.task_id if a.task_id else None,
                        "what_worked": a.what_worked,
                        "what_failed": a.what_failed,
                        "bottleneck": a.bottleneck,
                        "improvement_suggestion": a.improvement_suggestion,
                        "confidence": a.confidence,
                        "category": a.category,
                        "estimated_impact": a.estimated_impact,
                    }
                    for a in analyses
                ]
                response = client.table("critical_analyses").insert(analysis_rows).execute()
                if response.data:
                    logger.info(
                        "[ImprovementLoop] %d análises salvas no Supabase.", len(analyses)
                    )

            # Salva proposals
            if proposals:
                proposal_rows = [
                    {
                        "proposal_id": p.proposal_id,
                        "title": p.title,
                        "description": p.description,
                        "category": p.category,
                        "estimated_impact": p.estimated_impact,
                        "estimated_effort": p.estimated_effort,
                        "supporting_agents": p.supporting_analyses,
                        "status": p.status,
                        "votes": p.votes,
                        "community_reference": p.community_reference,
                    }
                    for p in proposals
                ]
                response = client.table("improvement_proposals").insert(proposal_rows).execute()
                if response.data:
                    logger.info(
                        "[ImprovementLoop] %d proposals salvas no Supabase.", len(proposals)
                    )

        except Exception as exc:
            logger.error(
                "[ImprovementLoop] Falha ao persistir no Supabase: %s", exc, exc_info=True
            )

    # ------------------------------------------------------------------
    # 6. Consultas
    # ------------------------------------------------------------------

    def get_pending_proposals(self) -> list[ImprovementProposal]:
        """
        Retorna proposals com status 'pending' aguardando decisão do usuário.

        Ordenadas por votes DESC para que as mais relevantes apareçam primeiro.

        Returns:
            Lista de ImprovementProposal com status == 'pending'.
        """
        pending = [p for p in self._pending_proposals if p.status == "pending"]
        pending.sort(key=lambda p: p.votes, reverse=True)
        return pending

    async def load_pending_from_supabase(self) -> list[ImprovementProposal]:
        """
        Carrega proposals pendentes do Supabase (para recuperação após restart).

        Returns:
            Lista de ImprovementProposal carregadas e adicionadas ao estado interno.
        """
        try:
            client = await self._get_client()
            response = (
                client.table("improvement_proposals")
                .select("*")
                .eq("status", "pending")
                .order("votes", desc=True)
                .execute()
            )

            loaded: list[ImprovementProposal] = []
            for row in response.data or []:
                proposal = ImprovementProposal(
                    proposal_id=row["proposal_id"],
                    title=row["title"],
                    description=row.get("description", ""),
                    category=row.get("category", "quality"),
                    estimated_impact=row.get("estimated_impact", "medium"),
                    estimated_effort=row.get("estimated_effort", "1d"),
                    supporting_analyses=row.get("supporting_agents", []),
                    status=row.get("status", "pending"),
                    created_at=str(row.get("created_at", "")),
                    votes=int(row.get("votes", 1)),
                    community_reference=row.get("community_reference", ""),
                )
                loaded.append(proposal)

            # Adiciona ao estado interno sem duplicar
            existing_ids = {p.proposal_id for p in self._pending_proposals}
            for p in loaded:
                if p.proposal_id not in existing_ids:
                    self._pending_proposals.append(p)

            logger.info(
                "[ImprovementLoop] %d proposals pendentes carregadas do Supabase.", len(loaded)
            )
            return loaded

        except Exception as exc:
            logger.error(
                "[ImprovementLoop] Falha ao carregar proposals do Supabase: %s",
                exc,
                exc_info=True,
            )
            return []

    async def get_improvement_metrics(self) -> dict:
        """
        Retorna métricas agregadas do ciclo de melhoria contínua.

        Útil para dashboards que mostram a evolução da qualidade do sistema.

        Returns:
            Dict com totais por status, categoria e impacto.
        """
        try:
            client = await self._get_client()
            response = client.table("improvement_proposals").select("*").execute()
            rows = response.data or []

            total = len(rows)
            by_status = {}
            by_category = {}
            by_impact = {}

            for row in rows:
                status = row.get("status", "unknown")
                category = row.get("category", "unknown")
                impact = row.get("estimated_impact", "unknown")

                by_status[status] = by_status.get(status, 0) + 1
                by_category[category] = by_category.get(category, 0) + 1
                by_impact[impact] = by_impact.get(impact, 0) + 1

            return {
                "total_proposals": total,
                "by_status": by_status,
                "by_category": by_category,
                "by_impact": by_impact,
                "approval_rate": (
                    round(by_status.get("approved", 0) / total * 100, 1)
                    if total > 0
                    else 0.0
                ),
            }

        except Exception as exc:
            logger.error(
                "[ImprovementLoop] Falha ao calcular métricas: %s", exc, exc_info=True
            )
            return {}

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _find_pending_proposal(self, proposal_id: str) -> Optional[ImprovementProposal]:
        """Encontra uma proposal pelo ID no estado interno."""
        for p in self._pending_proposals:
            if p.proposal_id == proposal_id:
                return p
        return None


# ---------------------------------------------------------------------------
# Instância global — importada pelos orquestradores e pela API
# ---------------------------------------------------------------------------

improvement_loop = ImprovementLoop()
