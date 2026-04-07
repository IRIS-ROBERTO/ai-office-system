"""
AI Office System — Marketing Team
AnalyticsAgent: Marketing Analytics Expert
Responsável por transformar dados brutos em insights acionáveis com relatórios precisos.
"""
from crewai import Agent

from backend.tools.ollama_tool import get_reasoning_llm
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType

# Metadados do agente (usados pelo Visual Engine e Event Bus)
agent_id: str = "mkt_analytics_01"
team: TeamType = TeamType.MARKETING
role_enum: AgentRole = AgentRole.ANALYTICS


def create_analytics_agent() -> Agent:
    """
    Instancia e retorna o AnalyticsAgent para o Marketing Team.
    LLM: DeepSeek R1 via Ollama — raciocínio analítico profundo para interpretação de dados.
    """
    llm = get_reasoning_llm()

    return Agent(
        role="Marketing Analytics Expert",
        goal=(
            "Transformar dados brutos em insights acionáveis com relatórios claros "
            "e recomendações precisas"
        ),
        backstory=(
            "Data-driven marketer com expertise em GA4, CRO (Conversion Rate Optimization) "
            "e attribution modeling multi-touch. Certificado em Google Analytics e HubSpot, "
            "com sólida base estatística para análise preditiva e testes A/B rigorosos. "
            "Traduz dashboards complexos em narrativas claras para stakeholders não-técnicos, "
            "sempre conectando métricas de vaidade a indicadores de negócio reais. Especializado "
            "em identificar gargalos no funil de conversão e propor otimizações baseadas em "
            "evidências, aumentando o ROI de campanhas em média 40% por ciclo."
        ),
        tools=[github_commit_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=8,
        memory=True,
    )
