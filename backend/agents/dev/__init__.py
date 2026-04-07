"""
AI Office System — Dev Team Agents
Ponto de entrada único para instanciar qualquer agente do time de desenvolvimento.

Uso:
    from backend.agents.dev import (
        create_planner_agent,
        create_frontend_agent,
        create_backend_agent,
        create_qa_agent,
        create_security_agent,
        create_docs_agent,
    )

    planner  = create_planner_agent()
    frontend = create_frontend_agent()
    backend  = create_backend_agent()
    qa       = create_qa_agent()
    security = create_security_agent()
    docs     = create_docs_agent()
"""

from backend.agents.dev.planner import create_planner_agent
from backend.agents.dev.frontend import create_frontend_agent
from backend.agents.dev.backend import create_backend_agent
from backend.agents.dev.qa import create_qa_agent
from backend.agents.dev.security import create_security_agent
from backend.agents.dev.docs import create_docs_agent

__all__ = [
    "create_planner_agent",
    "create_frontend_agent",
    "create_backend_agent",
    "create_qa_agent",
    "create_security_agent",
    "create_docs_agent",
]
