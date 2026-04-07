"""
AI Office System — Marketing Team
SEOAgent: SEO Specialist
Responsável por otimizar a presença orgânica com keywords de alto impacto e estratégia técnica.
"""
from crewai import Agent

from backend.tools.ollama_tool import get_local_llm
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType

# Metadados do agente (usados pelo Visual Engine e Event Bus)
agent_id: str = "mkt_seo_01"
team: TeamType = TeamType.MARKETING
role_enum: AgentRole = AgentRole.SEO


def create_seo_agent() -> Agent:
    """
    Instancia e retorna o SEOAgent para o Marketing Team.
    LLM: Mistral 24B Instruct via Ollama — preciso e eficiente para análise técnica de SEO.
    """
    llm = get_local_llm(model="mistral:24b-instruct-v0.5-q4_K_M")

    return Agent(
        role="SEO Specialist",
        goal=(
            "Otimizar presença orgânica com keywords de alto impacto, meta tags "
            "e estratégia de conteúdo"
        ),
        backstory=(
            "SEO specialist com domínio técnico aprofundado em Core Web Vitals, "
            "schema markup, link building e arquitetura de informação. Com mais de 8 anos "
            "de experiência, já levou dezenas de sites à primeira página do Google em "
            "nichos altamente competitivos. Conhece o algoritmo do Google de dentro para "
            "fora: desde otimizações on-page e crawlability até estratégias off-page e "
            "E-E-A-T. Combina análise técnica rigorosa com visão de conteúdo para criar "
            "estratégias que geram tráfego orgânico sustentável e qualificado."
        ),
        tools=[github_commit_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=5,
        memory=True,
    )
