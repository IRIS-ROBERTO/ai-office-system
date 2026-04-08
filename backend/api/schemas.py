"""
AI Office System — API Schemas
Pydantic models para request/response da API REST e WebSocket.
"""
from pydantic import BaseModel
from typing import Optional


class TaskRequest(BaseModel):
    request: str
    priority: int = 1


class TaskResponse(BaseModel):
    task_id: str
    status: str
    team: str
    created_at: str


class AgentStatus(BaseModel):
    agent_id: str
    role: str
    team: str
    status: str
    current_task_id: Optional[str] = None
    completed_tasks: int
    error_count: int = 0
    position: dict[str, int]


class SystemHealth(BaseModel):
    api: str
    redis: str
    ollama: str
    available_models: list[str]
    active_tasks: int


class EventHistoryResponse(BaseModel):
    events: list[dict]
    total: int
