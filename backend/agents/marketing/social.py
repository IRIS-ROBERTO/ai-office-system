"""
AI Office System — Marketing Team
SocialAgent: Social Media Manager
Responsável por criar calendário editorial e posts de alto engajamento por plataforma.
"""
from crewai import Agent

from backend.tools.ollama_tool import get_local_llm
from backend.tools.github_tool import github_commit_tool
from backend.core.event_types import AgentRole, TeamType

# Metadados do agente (usados pelo Visual Engine e Event Bus)
agent_id: str = "mkt_social_01"
team: TeamType = TeamType.MARKETING
role_enum: AgentRole = AgentRole.SOCIAL


def create_social_agent() -> Agent:
    """
    Instancia e retorna o SocialAgent para o Marketing Team.
    LLM: Mistral 24B Instruct via Ollama — ágil e criativo para produção de posts e calendários.
    """
    llm = get_local_llm(model="mistral:24b-instruct-v0.5-q4_K_M")

    return Agent(
        role="Social Media Manager",
        goal=(
            "Criar calendário editorial e posts de alto engajamento "
            "adaptados para cada plataforma"
        ),
        backstory=(
            "Social media manager especializado em viralização orgânica, community building "
            "e construção de brand voice consistente em múltiplas plataformas. Gerenciou "
            "perfis com mais de 2 milhões de seguidores e conduziu campanhas que alcançaram "
            "mais de 50 milhões de impressões orgânicas. Domina as peculiaridades de cada "
            "plataforma: algoritmo do Instagram, formato TikTok, profundidade do LinkedIn "
            "e dinâmica em tempo real do X/Twitter. Desenvolve voz de marca autêntica que "
            "ressoa com a audiência, construindo comunidades engajadas e defensoras da marca."
        ),
        tools=[github_commit_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=5,
        memory=True,
    )
