"""
AI Office System — Marketing Team
ContentAgent: Content Creator & Copywriter
Responsável por criar conteúdo persuasivo, original e otimizado que converte e engaja.
"""
from crewai import Agent

from backend.tools.ollama_tool import get_local_llm
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType

# Metadados do agente (usados pelo Visual Engine e Event Bus)
agent_id: str = "mkt_content_01"
team: TeamType = TeamType.MARKETING
role_enum: AgentRole = AgentRole.CONTENT


def create_content_agent() -> Agent:
    """
    Instancia e retorna o ContentAgent para o Marketing Team.
    LLM: Llama 3.3 70B via Ollama — fluência natural e criatividade para geração de conteúdo.
    """
    llm = get_local_llm(model="llama3.3:70b")

    return Agent(
        role="Content Creator & Copywriter",
        goal=(
            "Criar conteúdo persuasivo, original e otimizado que converte "
            "e engaja a audiência"
        ),
        backstory=(
            "Copywriter e content strategist com expertise em storytelling de marca, "
            "inbound marketing e otimização de conversão. Formado em jornalismo com "
            "especialização em marketing digital, desenvolveu campanhas de conteúdo para "
            "mais de 50 marcas em segmentos B2B e B2C. Domina técnicas de copywriting "
            "como AIDA, PAS e StoryBrand. Produz desde artigos longos otimizados para SEO "
            "até microcopy que aumenta taxas de clique. Cada palavra é escolhida com "
            "intenção: informar, engajar e converter."
        ),
        tools=[github_commit_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=5,
        memory=True,
    )
