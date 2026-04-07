"""
AI Office System — Marketing Team Agents
Exporta todas as factory functions para instanciar os agentes do time de marketing.

Uso:
    from backend.agents.marketing import (
        create_research_agent,
        create_strategy_agent,
        create_content_agent,
        create_seo_agent,
        create_social_agent,
        create_analytics_agent,
    )
"""
from backend.agents.marketing.research import create_research_agent
from backend.agents.marketing.strategy import create_strategy_agent
from backend.agents.marketing.content import create_content_agent
from backend.agents.marketing.seo import create_seo_agent
from backend.agents.marketing.social import create_social_agent
from backend.agents.marketing.analytics import create_analytics_agent

__all__ = [
    "create_research_agent",
    "create_strategy_agent",
    "create_content_agent",
    "create_seo_agent",
    "create_social_agent",
    "create_analytics_agent",
]
