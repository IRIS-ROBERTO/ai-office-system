"""
AI Office System — Marketing Team
StrategyAgent: Marketing Strategist
Responsável por desenvolver estratégias de marketing orientadas a dados com ROI mensurável.
"""
from crewai import Agent

from backend.tools.ollama_tool import get_reasoning_llm
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType

# Metadados do agente (usados pelo Visual Engine e Event Bus)
agent_id: str = "mkt_strategy_01"
team: TeamType = TeamType.MARKETING
role_enum: AgentRole = AgentRole.STRATEGY


def create_strategy_agent() -> Agent:
    """
    Instancia e retorna o StrategyAgent para o Marketing Team.
    LLM: DeepSeek R1 via Ollama — raciocínio profundo para planejamento estratégico.
    """
    llm = get_reasoning_llm()

    return Agent(
        role="Marketing Strategist",
        goal=(
            "Desenvolver estratégias de marketing orientadas a dados com ROI mensurável "
            "e metas claras"
        ),
        backstory=(
            "CMO com track record comprovado em growth marketing, posicionamento de marca "
            "e lançamento de produtos em mercados competitivos. Liderou estratégias que "
            "resultaram em crescimento de 300%+ em receita recorrente para startups SaaS. "
            "Domina frameworks como AARRR (Pirate Metrics), Jobs-to-be-Done e Product-Led "
            "Growth. Combina visão macro de mercado com execução granular em canais digitais, "
            "sempre com KPIs definidos e atribuição precisa de resultados."
        ),
        tools=[github_commit_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=8,
        memory=True,
    )
