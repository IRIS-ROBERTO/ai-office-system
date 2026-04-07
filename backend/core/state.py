"""
AI Office System — LangGraph State
Estado global compartilhado entre todos os nós do grafo.
TypedDict garante type safety em todo o fluxo LangGraph.
"""
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages


class TaskState(TypedDict):
    """Estado de uma tarefa em execução no grafo LangGraph."""
    task_id: str
    team: str                          # "dev" | "marketing"
    original_request: str              # Input humano bruto
    senior_directive: Optional[str]    # Output do Senior Agent (Sonnet)
    subtasks: list[dict]               # Lista quebrada pelo Planner
    current_subtask_index: int
    agent_outputs: dict[str, str]      # agent_id → resultado
    quality_approved: bool
    retry_count: int
    final_output: Optional[str]
    errors: list[str]
    messages: Annotated[list, add_messages]  # LangGraph message history


class AgentState(TypedDict):
    """Estado de um agente individual durante execução."""
    agent_id: str
    agent_role: str
    team: str
    status: str                        # "idle" | "thinking" | "working" | "moving"
    current_task_id: Optional[str]
    position: dict                     # {"x": int, "y": int} para visual engine
    completed_tasks: int
    error_count: int


class SystemState(TypedDict):
    """Estado global do escritório inteiro."""
    active_tasks: dict[str, TaskState]
    agents: dict[str, AgentState]
    dev_team_busy: bool
    marketing_team_busy: bool
    total_tasks_completed: int
    total_tokens_used: int
    uptime_seconds: float
