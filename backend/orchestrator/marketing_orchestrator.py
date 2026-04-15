"""
AI Office System — MarketingOrchestrator
LangGraph orchestrator specialised for the digital marketing team.

Coordinates 6 CrewAI agents (research, strategy, content, seo, social, analytics)
through the BaseOrchestrator pipeline with a marketing-specific senior context
that mandates concrete, measurable deliverables for every subtask.
"""
import logging

from crewai import Crew, Process

from backend.agents.marketing import (
    create_analytics_agent,
    create_content_agent,
    create_research_agent,
    create_seo_agent,
    create_social_agent,
    create_strategy_agent,
)
from backend.core.event_types import TeamType
from backend.orchestrator.base_orchestrator import BaseOrchestrator

logger = logging.getLogger(__name__)

_MKT_CONTEXT = (
    "Você está coordenando um time de marketing digital. "
    "Sempre produza entregáveis concretos e mensuráveis.\n\n"
    "O time é composto por:\n"
    "- research: Market Researcher — análise de mercado, personas, concorrência\n"
    "- strategy: Marketing Strategist — planejamento estratégico, KPIs, roadmap\n"
    "- content: Content Creator — copywriting, blog posts, email sequences\n"
    "- seo: SEO Specialist — keyword research, on-page, link building\n"
    "- social: Social Media Manager — calendário de posts, engajamento, growth\n"
    "- analytics: Data Analyst — dashboards, atribuição, relatórios de ROI\n\n"
    "Princípios inegociáveis:\n"
    "1. Todo entregável deve ter métricas de sucesso definidas antes de começar.\n"
    "2. Critérios de aceitação devem ser mensuráveis (ex.: 'CTR > 2%', "
    "'100 palavras-chave mapeadas', '30 posts planejados').\n"
    "3. Cada subtarefa deve produzir um artefato concreto: documento, planilha, "
    "calendário, relatório ou copy pronto para publicação.\n"
    "4. Analytics deve validar toda estratégia com dados antes de executar."
)


class MarketingOrchestrator(BaseOrchestrator):
    """
    Orchestrator for the Marketing Team.

    Uses Process.sequential so research informs strategy, strategy guides
    content, content feeds SEO, and analytics closes the loop.
    """

    def __init__(self) -> None:
        super().__init__(team=TeamType.MARKETING)
        logger.info("[MarketingOrchestrator] Instanciado para o Marketing Team.")

    # ------------------------------------------------------------------
    # Abstract implementations
    # ------------------------------------------------------------------

    @property
    def _senior_system_context(self) -> str:
        return _MKT_CONTEXT

    def _build_crew(self) -> Crew:
        """
        Builds a CrewAI Crew with all 6 Marketing Team agents.
        Process.sequential keeps the research → strategy → execution chain intact.
        """
        research = create_research_agent()
        strategy = create_strategy_agent()
        content = create_content_agent()
        seo = create_seo_agent()
        social = create_social_agent()
        analytics = create_analytics_agent()

        crew = Crew(
            agents=[research, strategy, content, seo, social, analytics],
            tasks=[],          # Tasks are injected dynamically per subtask
            process=Process.sequential,
            verbose=False,
            # CrewAI memory estava quebrando o runtime local por exigir
            # configuração adicional de embeddings no ambiente.
            # Mantemos o fluxo determinístico sem bloquear a entrega.
            memory=False,
        )

        logger.info(
            "[MarketingOrchestrator] Crew construída com 6 agentes: "
            "research, strategy, content, seo, social, analytics."
        )
        return crew
