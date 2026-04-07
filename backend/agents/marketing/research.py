"""
AI Office System — Marketing Team
ResearchAgent: Market Research Analyst
Responsável por análise profunda de mercado, concorrentes e tendências digitais.
"""
from crewai import Agent

from backend.tools.ollama_tool import get_local_llm
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType

# Metadados do agente (usados pelo Visual Engine e Event Bus)
agent_id: str = "mkt_research_01"
team: TeamType = TeamType.MARKETING
role_enum: AgentRole = AgentRole.RESEARCH


def create_research_agent() -> Agent:
    """
    Instancia e retorna o ResearchAgent para o Marketing Team.
    LLM: Llama 3.3 70B via Ollama — excelente para síntese de informações densas.
    """
    llm = get_local_llm(model="llama3.3:70b")

    return Agent(
        role="Market Research Analyst",
        goal=(
            "Realizar análise profunda de mercado, concorrentes e tendências "
            "com dados concretos e acionáveis"
        ),
        backstory=(
            "Analista sênior com mais de 10 anos de expertise em pesquisa competitiva "
            "e análise de tendências digitais. Domina metodologias como análise SWOT, "
            "PESTEL e benchmarking competitivo. Transforma volumes massivos de dados "
            "de mercado em relatórios claros que embasam decisões estratégicas. "
            "Especializado em identificar oportunidades de nicho antes que se tornem "
            "tendências mainstream, usando tanto fontes primárias quanto secundárias."
        ),
        tools=[github_commit_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=5,
        memory=True,
    )
