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


class ServiceRequestCreate(BaseModel):
    title: str
    team: str
    request: str
    requester_name: Optional[str] = None
    requester_team: Optional[str] = None
    urgency: str = "medium"
    desired_due_date: Optional[str] = None
    acceptance_criteria: Optional[str] = None


class ServiceRequestResponse(BaseModel):
    request_id: str
    title: str
    team: str
    status: str
    stage_label: str
    requester_name: Optional[str] = None
    requester_team: Optional[str] = None
    urgency: str
    priority: int
    desired_due_date: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    request: str
    task_id: Optional[str] = None
    current_agent_role: Optional[str] = None
    tested_by_team: bool
    approved_by_orchestrator: bool
    created_at: str
    updated_at: str


class ServiceRequestListResponse(BaseModel):
    items: list[ServiceRequestResponse]
    total: int
