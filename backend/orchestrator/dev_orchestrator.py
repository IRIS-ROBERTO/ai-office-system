"""
AI Office System — DevOrchestrator
LangGraph orchestrator specialised for the software development team.

Coordinates 6 CrewAI agents (planner, frontend, backend, qa, security, docs)
through the BaseOrchestrator pipeline with a software-engineering-specific
senior context injected into every Senior LLM call.
"""
import logging

from crewai import Crew, Process

from backend.agents.dev import (
    create_backend_agent,
    create_docs_agent,
    create_frontend_agent,
    create_planner_agent,
    create_qa_agent,
    create_security_agent,
)
from backend.core.event_types import TeamType
from backend.orchestrator.base_orchestrator import BaseOrchestrator

logger = logging.getLogger(__name__)

_DEV_CONTEXT = (
    "Você está coordenando um time de desenvolvimento de software. "
    "Sempre gere subtasks com código funcional.\n\n"
    "O time é composto por:\n"
    "- planner: Arquiteto Sênior — decompõe requisitos em plano técnico\n"
    "- frontend: Frontend Engineer — React, Next.js, TypeScript, PixiJS\n"
    "- backend: Backend Engineer — FastAPI, PostgreSQL, Redis, Python\n"
    "- qa: QA Engineer — testes automatizados, cobertura, integração\n"
    "- security: Security Engineer — OWASP, pen-test, hardening\n"
    "- docs: Technical Writer — README, OpenAPI, ADRs\n\n"
    "Princípios inegociáveis:\n"
    "1. Cada subtarefa deve produzir código funcional e testado.\n"
    "2. Critérios de aceitação devem ser verificáveis (ex.: 'API retorna 200', "
    "'cobertura > 80%').\n"
    "3. Segurança é requisito, não opcional — security deve revisar todo output crítico.\n"
    "4. Documentação é entregável de primeira classe, não afterthought."
)


class DevOrchestrator(BaseOrchestrator):
    """
    Orchestrator for the Dev Team.

    Uses Process.sequential so each CrewAI agent runs in order, making
    it easy to pass outputs as context to the next agent.
    """

    def __init__(self) -> None:
        super().__init__(team=TeamType.DEV)
        logger.info("[DevOrchestrator] Instanciado para o Dev Team.")

    # ------------------------------------------------------------------
    # Abstract implementations
    # ------------------------------------------------------------------

    @property
    def _senior_system_context(self) -> str:
        return _DEV_CONTEXT

    def _build_crew(self) -> Crew:
        """
        Builds a CrewAI Crew with all 6 Dev Team agents.
        Process.sequential ensures deterministic execution order.
        """
        planner = create_planner_agent()
        frontend = create_frontend_agent()
        backend = create_backend_agent()
        qa = create_qa_agent()
        security = create_security_agent()
        docs = create_docs_agent()

        crew = Crew(
            agents=[planner, frontend, backend, qa, security, docs],
            tasks=[],          # Tasks are injected dynamically per subtask
            process=Process.sequential,
            verbose=True,
            memory=False,      # Memory managed by LangGraph state, not CrewAI
        )

        logger.info(
            "[DevOrchestrator] Crew construída com 6 agentes: "
            "planner, frontend, backend, qa, security, docs."
        )
        return crew
