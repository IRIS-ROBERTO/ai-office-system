"""
Agent Factory — cria agentes dinamicamente baseado em:
1. Tipo de tarefa recebida
2. Recursos disponíveis na máquina
3. Modelos Ollama disponíveis

O orquestrador não precisa conhecer os agentes individualmente.
Ele diz: "preciso de 3 agentes de código e 2 de QA"
A factory retorna os agentes configurados e prontos.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

from crewai import Agent, Process

from backend.config.settings import settings
from backend.core.event_types import AgentRole, TeamType
from backend.core.resource_monitor import ResourceMonitor, get_capacity_report
from backend.tools.ollama_tool import get_llm_for_role

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapeamento de roles para times
# ---------------------------------------------------------------------------

_DEV_ROLES: list[str] = [
    AgentRole.PLANNER.value,
    AgentRole.FRONTEND.value,
    AgentRole.BACKEND.value,
    AgentRole.QA.value,
    AgentRole.SECURITY.value,
    AgentRole.DOCS.value,
]

_MARKETING_ROLES: list[str] = [
    AgentRole.RESEARCH.value,
    AgentRole.STRATEGY.value,
    AgentRole.CONTENT.value,
    AgentRole.SEO.value,
    AgentRole.SOCIAL.value,
    AgentRole.ANALYTICS.value,
]

# Configuração de cada role: role_label, goal, backstory
_ROLE_PROFILES: dict[str, dict] = {
    # Dev Team
    AgentRole.PLANNER.value: {
        "role_label": "Software Architect & Task Planner",
        "goal": (
            "Quebrar requisitos em subtarefas técnicas claras e sequenciadas "
            "com critérios de aceitação definidos."
        ),
        "backstory": (
            "Arquiteto sênior com 15 anos de experiência em sistemas distribuídos. "
            "Domina decomposição de problemas complexos, definição de contratos de API "
            "e criação de ADRs que o time inteiro consegue seguir."
        ),
    },
    AgentRole.FRONTEND.value: {
        "role_label": "Frontend Engineer",
        "goal": (
            "Implementar interfaces de alta qualidade com React, Next.js e TypeScript, "
            "garantindo acessibilidade, performance e responsividade."
        ),
        "backstory": (
            "Engenheira frontend com foco em experiência do usuário e código limpo. "
            "Especialista em React 18, Next.js App Router, Tailwind CSS e animações com PixiJS. "
            "Nunca entrega componente sem testes unitários e stories documentadas."
        ),
    },
    AgentRole.BACKEND.value: {
        "role_label": "Backend Engineer",
        "goal": (
            "Desenvolver APIs RESTful e lógica de negócio robustas com FastAPI, "
            "garantindo performance, escalabilidade e integridade dos dados."
        ),
        "backstory": (
            "Engenheiro backend especializado em Python, FastAPI, PostgreSQL e Redis. "
            "Obcecado por cobertura de testes, migrations seguras e contratos de API claros."
        ),
    },
    AgentRole.QA.value: {
        "role_label": "QA Engineer",
        "goal": (
            "Garantir qualidade do software através de testes automatizados, "
            "análise de cobertura e detecção de regressões antes do deploy."
        ),
        "backstory": (
            "Engenheiro de qualidade com expertise em pytest, Playwright e testes de contrato. "
            "Acredita que QA começa no design, não depois da implementação."
        ),
    },
    AgentRole.SECURITY.value: {
        "role_label": "Security Engineer",
        "goal": (
            "Identificar e mitigar vulnerabilidades de segurança no código e na infraestrutura, "
            "seguindo OWASP Top 10 e princípios de defense-in-depth."
        ),
        "backstory": (
            "Especialista em segurança ofensiva e defensiva. Realiza code review focado em "
            "injeção, autenticação, autorização e exposição de dados sensíveis."
        ),
    },
    AgentRole.DOCS.value: {
        "role_label": "Technical Writer",
        "goal": (
            "Produzir documentação técnica clara, completa e mantível — "
            "READMEs, OpenAPI specs, ADRs e guias de onboarding."
        ),
        "backstory": (
            "Technical writer com background em engenharia de software. "
            "Transforma código complexo em documentação que qualquer desenvolvedor consegue seguir."
        ),
    },
    # Marketing Team
    AgentRole.RESEARCH.value: {
        "role_label": "Market Research Analyst",
        "goal": (
            "Coletar e sintetizar dados de mercado, concorrentes e tendências "
            "para embasar decisões estratégicas de marketing."
        ),
        "backstory": (
            "Analista com experiência em pesquisa qualitativa e quantitativa. "
            "Transforma dados brutos em insights acionáveis com clareza e precisão."
        ),
    },
    AgentRole.STRATEGY.value: {
        "role_label": "Marketing Strategist",
        "goal": (
            "Desenvolver estratégias de go-to-market, posicionamento e campanhas "
            "alinhadas aos objetivos de negócio e ao público-alvo."
        ),
        "backstory": (
            "Estrategista com track record em lançamentos B2B e B2C. "
            "Traduz pesquisa de mercado em planos executáveis com KPIs claros."
        ),
    },
    AgentRole.CONTENT.value: {
        "role_label": "Content Creator",
        "goal": (
            "Produzir conteúdo persuasivo e relevante que engaje o público-alvo, "
            "fortaleça a marca e suporte objetivos de conversão."
        ),
        "backstory": (
            "Redatora criativa com experiência em copywriting, storytelling e conteúdo editorial. "
            "Adapta tom e estilo ao canal e ao público sem perder a voz da marca."
        ),
    },
    AgentRole.SEO.value: {
        "role_label": "SEO Specialist",
        "goal": (
            "Otimizar conteúdo e estrutura técnica para motores de busca, "
            "aumentando visibilidade orgânica e tráfego qualificado."
        ),
        "backstory": (
            "Especialista em SEO técnico e on-page. Domina análise de palavras-chave, "
            "arquitetura de links internos e otimização de Core Web Vitals."
        ),
    },
    AgentRole.SOCIAL.value: {
        "role_label": "Social Media Manager",
        "goal": (
            "Criar e gerenciar conteúdo para redes sociais que aumente engajamento, "
            "seguidores e percepção positiva da marca."
        ),
        "backstory": (
            "Manager com domínio de Instagram, LinkedIn, X e TikTok. "
            "Sabe o que performa em cada plataforma e produz conteúdo nativo com agilidade."
        ),
    },
    AgentRole.ANALYTICS.value: {
        "role_label": "Marketing Analytics Specialist",
        "goal": (
            "Analisar dados de campanhas, comportamento de usuários e funil de conversão "
            "para otimizar performance e embasar decisões com evidências."
        ),
        "backstory": (
            "Analista com expertise em GA4, Mixpanel e SQL. "
            "Converte dados de marketing em relatórios executivos claros e recomendações concretas."
        ),
    },
    # Orchestrator
    AgentRole.ORCHESTRATOR.value: {
        "role_label": "Senior Orchestrator",
        "goal": (
            "Coordenar times de agentes especializados, decompor tarefas complexas "
            "e garantir qualidade dos entregáveis finais."
        ),
        "backstory": (
            "Orquestrador sênior com visão sistêmica de projetos de software e marketing. "
            "Garante alinhamento entre times, critérios de aceitação e prazos."
        ),
    },
}

# Complexidade → contagem de agentes por tipo de tarefa
_COMPLEXITY_AGENT_COUNT: dict[str, dict[str, int]] = {
    "simple": {"dev": 2, "marketing": 2, "total": 3},
    "medium": {"dev": 4, "marketing": 3, "total": 6},
    "complex": {"dev": 6, "marketing": 6, "total": 12},  # máximo — ajustado pelo monitor
}

# Roles prioritários por complexidade (subsets para simple/medium)
_DEV_ROLES_PRIORITY: list[str] = [
    AgentRole.PLANNER.value,
    AgentRole.BACKEND.value,
    AgentRole.FRONTEND.value,
    AgentRole.QA.value,
    AgentRole.SECURITY.value,
    AgentRole.DOCS.value,
]

_MARKETING_ROLES_PRIORITY: list[str] = [
    AgentRole.STRATEGY.value,
    AgentRole.CONTENT.value,
    AgentRole.RESEARCH.value,
    AgentRole.SEO.value,
    AgentRole.SOCIAL.value,
    AgentRole.ANALYTICS.value,
]


class AgentFactory:
    """
    Fábrica dinâmica de agentes CrewAI.

    Consulta ResourceMonitor para adaptar modelo e quantidade de agentes
    aos recursos reais da máquina antes de cada instanciação.
    """

    def __init__(self) -> None:
        self._monitor = ResourceMonitor()

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------

    async def create_agents_for_task(
        self,
        task_type: str,
        task_complexity: str,
    ) -> list[Agent]:
        """
        Cria e retorna uma lista de agentes CrewAI prontos para uso.

        Args:
            task_type:       "dev" | "marketing" | "mixed"
            task_complexity: "simple" | "medium" | "complex"

        Complexidade → contagem de agentes:
            simple  → 2-3 agentes
            medium  → 4-6 agentes
            complex → máximo suportado pelo resource_monitor (até 12)

        Returns:
            Lista de crewai.Agent configurados e prontos.
        """
        # 1. Verificar recursos disponíveis
        capacity = await get_capacity_report()
        resources = capacity["resources"]
        max_agents = capacity["max_agents"]

        # 2. Determinar distribuição ideal
        counts = self.get_optimal_agent_count(resources, task_complexity)
        total = min(counts["total"], max_agents)

        logger.info(
            "[AgentFactory] task_type=%s complexity=%s | "
            "max_agents=%d | planejado=%d | motivo=%s",
            task_type,
            task_complexity,
            max_agents,
            total,
            counts["reasoning"],
        )

        # 3. Montar lista de roles a instanciar
        roles_to_create = self._select_roles(task_type, task_complexity, total, counts)

        # 4. Instanciar agentes com modelos adaptados aos recursos
        agents: list[Agent] = []
        for role in roles_to_create:
            try:
                agent = await self._build_agent(role, resources, model_override=None)
                agents.append(agent)
            except Exception as exc:
                logger.error(
                    "[AgentFactory] Falha ao criar agente role=%s: %s", role, exc
                )

        logger.info(
            "[AgentFactory] %d agentes criados para task_type=%s complexity=%s.",
            len(agents),
            task_type,
            task_complexity,
        )
        return agents

    async def create_specialist_agent(
        self,
        role: str,
        model_override: Optional[str] = None,
    ) -> Agent:
        """
        Cria um único agente especialista.

        Args:
            role:           Qualquer valor de AgentRole (ex.: "backend", "content").
            model_override: Se fornecido, usa este model_id em vez do selecionado
                            automaticamente pelo resource_monitor.

        Returns:
            crewai.Agent configurado e pronto.
        """
        resources = await self._monitor.get_system_resources()
        agent = await self._build_agent(role, resources, model_override=model_override)
        logger.info(
            "[AgentFactory] Agente especialista criado: role=%s model=%s",
            role,
            model_override or "auto",
        )
        return agent

    def get_optimal_agent_count(self, resources: dict, task_complexity: str) -> dict:
        """
        Calcula distribuição ideal de agentes por tipo.

        Args:
            resources:        Output de get_system_resources().
            task_complexity:  "simple" | "medium" | "complex"

        Returns:
            {
                "total":             int,
                "dev_agents":        int,
                "marketing_agents":  int,
                "reasoning":         str,  # "12GB RAM → 3 agentes simultâneos"
            }
        """
        ram_available_gb: float = resources.get("ram_available_gb", 0.0)
        cpu_usage_pct: float = resources.get("cpu_usage_pct", 0.0)
        gpu_vram_free_gb: float = resources.get("gpu_vram_free_gb", 0.0)
        gpu_available: bool = resources.get("gpu_available", False)

        # Calcular capacidade máxima real
        max_by_resources = self._monitor.calculate_max_agents(resources)

        # Contagens desejadas por complexidade
        desired = _COMPLEXITY_AGENT_COUNT.get(task_complexity, _COMPLEXITY_AGENT_COUNT["medium"])
        desired_total = desired["total"]

        # Respeitar limite da máquina
        total = min(desired_total, max_by_resources)

        # Distribuição equitativa dev/marketing
        dev_agents = min(desired["dev"], math.ceil(total / 2))
        marketing_agents = min(desired["marketing"], total - dev_agents)

        # Construir mensagem de raciocínio
        parts: list[str] = [f"{ram_available_gb:.0f} GB RAM"]
        if gpu_available and gpu_vram_free_gb > 0:
            parts.append(f"{gpu_vram_free_gb:.0f} GB VRAM")
        if cpu_usage_pct > 80:
            parts.append(f"CPU {cpu_usage_pct:.0f}% (redução aplicada)")
        reasoning = (
            f"{' + '.join(parts)} → {total} agentes simultâneos "
            f"({dev_agents} dev, {marketing_agents} marketing)"
        )

        return {
            "total": total,
            "dev_agents": dev_agents,
            "marketing_agents": marketing_agents,
            "reasoning": reasoning,
        }

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def _select_roles(
        self,
        task_type: str,
        task_complexity: str,
        total: int,
        counts: dict,
    ) -> list[str]:
        """
        Monta a lista ordenada de roles a instanciar respeitando
        o total calculado e o tipo de tarefa.
        """
        dev_slots = counts["dev_agents"]
        mkt_slots = counts["marketing_agents"]

        selected: list[str] = []

        if task_type == "dev":
            # Apenas dev, usa todo o slot disponível
            selected = _DEV_ROLES_PRIORITY[:total]

        elif task_type == "marketing":
            # Apenas marketing
            selected = _MARKETING_ROLES_PRIORITY[:total]

        else:
            # mixed — intercala dev e marketing por prioridade
            dev_roles = _DEV_ROLES_PRIORITY[:dev_slots]
            mkt_roles = _MARKETING_ROLES_PRIORITY[:mkt_slots]
            # Intercala para variedade
            selected = []
            max_len = max(len(dev_roles), len(mkt_roles))
            for i in range(max_len):
                if i < len(dev_roles):
                    selected.append(dev_roles[i])
                if i < len(mkt_roles):
                    selected.append(mkt_roles[i])
            selected = selected[:total]

        logger.debug("[AgentFactory] Roles selecionados: %s", selected)
        return selected

    async def _build_agent(
        self,
        role: str,
        resources: dict,
        model_override: Optional[str] = None,
    ) -> Agent:
        """
        Instancia um crewai.Agent para o role dado.

        Seleciona o modelo via resource_monitor (ou usa model_override).
        Usa get_llm_for_role() do ollama_tool como base, mas substitui
        o modelo caso o resource_monitor aponte outro mais adequado.
        """
        profile = _ROLE_PROFILES.get(role)
        if profile is None:
            logger.warning(
                "[AgentFactory] Perfil não encontrado para role='%s' — usando orchestrator.",
                role,
            )
            profile = _ROLE_PROFILES[AgentRole.ORCHESTRATOR.value]

        # Selecionar LLM
        if model_override:
            # Override explícito: usar ollama direto com modelo especificado
            from langchain_ollama import ChatOllama

            llm = ChatOllama(
                model=model_override,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=0.1,
                num_predict=settings.LOCAL_MAX_TOKENS,
            )
            model_used = model_override
        else:
            # Verificar se o resource_monitor recomenda um modelo diferente
            recommended = self._monitor.get_recommended_model_for_resources(resources, role)
            default_model = self._get_default_model_for_role(role)

            if recommended != default_model:
                logger.info(
                    "[AgentFactory] role=%s: resource_monitor recomenda '%s' "
                    "(padrão seria '%s')",
                    role,
                    recommended,
                    default_model,
                )
                from langchain_ollama import ChatOllama

                llm = ChatOllama(
                    model=recommended,
                    base_url=settings.OLLAMA_BASE_URL,
                    temperature=0.1,
                    num_predict=settings.LOCAL_MAX_TOKENS,
                )
                model_used = recommended
            else:
                # Usar roteamento padrão do ollama_tool
                llm = get_llm_for_role(role)
                model_used = default_model

        agent = Agent(
            role=profile["role_label"],
            goal=profile["goal"],
            backstory=profile["backstory"],
            llm=llm,
            tools=[],          # Tools injetadas pelo orquestrador se necessário
            verbose=True,
            allow_delegation=False,
            max_iter=settings.MAX_RETRIES_PER_SUBTASK * 3,
            memory=True,
        )

        # Metadados dinâmicos para rastreamento
        agent.agent_id = f"{role}_factory_{id(agent)}"    # type: ignore[attr-defined]
        agent.role_key = role                              # type: ignore[attr-defined]
        agent.model_used = model_used                      # type: ignore[attr-defined]

        logger.debug(
            "[AgentFactory] Agent criado: role=%s label='%s' model=%s",
            role,
            profile["role_label"],
            model_used,
        )
        return agent

    def _get_default_model_for_role(self, role: str) -> str:
        """
        Retorna o model_id padrão mapeado pelo ollama_tool para um dado role.
        Usado para comparar com a recomendação do resource_monitor.
        """
        code_roles = {"planner", "frontend", "backend"}
        vision_roles = {"qa", "security", "analytics"}
        docs_roles = {"docs"}
        fast_roles = {"seo", "social"}
        orchestrator_roles = {"orchestrator"}

        if role in code_roles:
            return settings.LOCAL_MODEL_CODE
        if role in vision_roles:
            return settings.LOCAL_MODEL_VISION
        if role in docs_roles:
            return settings.LOCAL_MODEL_DOCS
        if role in fast_roles:
            return settings.LOCAL_MODEL_FAST
        if role in orchestrator_roles:
            # Senior usa Gemini/OpenRouter — sem modelo local padrão
            return settings.LOCAL_MODEL_CODE
        return settings.LOCAL_MODEL_GENERAL


# ---------------------------------------------------------------------------
# Singleton de módulo — instância padrão para uso direto
# ---------------------------------------------------------------------------

_factory = AgentFactory()


async def create_agents_for_task(task_type: str, task_complexity: str) -> list[Agent]:
    """Atalho de módulo para AgentFactory().create_agents_for_task()."""
    return await _factory.create_agents_for_task(task_type, task_complexity)


async def create_specialist_agent(
    role: str, model_override: Optional[str] = None
) -> Agent:
    """Atalho de módulo para AgentFactory().create_specialist_agent()."""
    return await _factory.create_specialist_agent(role, model_override)


def get_optimal_agent_count(resources: dict, task_complexity: str) -> dict:
    """Atalho de módulo para AgentFactory().get_optimal_agent_count()."""
    return _factory.get_optimal_agent_count(resources, task_complexity)
