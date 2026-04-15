"""
AI Office System — API Schemas
Pydantic models para request/response da API REST e WebSocket.
"""
from pydantic import BaseModel, Field
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


class AgentCapabilities(BaseModel):
    agent_id: str
    role: str
    team: str
    tool_policy: dict
    picoclaw: dict


class AgentPersonalityConfig(BaseModel):
    agent_id: str
    role: str
    team: str
    persona_name: str
    mission: str
    personality: list[str]
    operating_rules: list[str]
    autonomy_level: str
    model_policy: str
    visibility_level: str
    updated_at: Optional[str] = None


class AgentPersonalityUpdate(BaseModel):
    persona_name: Optional[str] = None
    mission: Optional[str] = None
    personality: Optional[list[str]] = None
    operating_rules: Optional[list[str]] = None
    autonomy_level: Optional[str] = None
    model_policy: Optional[str] = None
    visibility_level: Optional[str] = None


class SystemHealth(BaseModel):
    api: str
    redis: str
    event_bus: str
    event_bus_persistent: bool
    ollama: str
    available_models: list[str]
    brain_router: dict
    model_gate: dict
    picoclaw: dict
    active_tasks: int


class EventHistoryResponse(BaseModel):
    events: list[dict]
    total: int


class DeliveryAuditItem(BaseModel):
    task_id: str
    subtask_id: str
    agent_id: str
    agent_role: str
    team: str
    approved: bool
    feedback: str
    created_at: str
    manifest_path: str
    failed_stages: list[str]
    stage_count: int
    functional_ready: bool
    functional_message: str = ""
    commit_sha: str = ""
    commit_message: str = ""
    repo_path: str = ""
    files_changed: list[str] = Field(default_factory=list)
    pushed: Optional[bool] = None
    stages: list[dict] = Field(default_factory=list)


class DeliveryAuditListResponse(BaseModel):
    total: int
    returned: int
    approved: int
    failed: int
    functional_ready: int
    items: list[DeliveryAuditItem]


class DeliveryAuditTaskResponse(BaseModel):
    task_id: str
    total: int
    approved: int
    failed: int
    functional_ready: int
    commits: list[dict]
    items: list[DeliveryAuditItem]


class ProductionReadinessResponse(BaseModel):
    status: str
    score: int
    production_ready: bool
    blockers: list[dict]
    warnings: list[dict]
    runtime: dict
    delivery_audit: dict
    git: dict
    next_actions: list[str]


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
    last_execution_message: Optional[str] = None
    last_execution_stage: Optional[str] = None
    execution_log_size: int = 0
    created_at: str
    updated_at: str


class ServiceRequestListResponse(BaseModel):
    items: list[ServiceRequestResponse]
    total: int


class ExecutionLogEntryResponse(BaseModel):
    timestamp: str
    stage: str
    message: str
    level: str
    team: str
    task_id: str
    agent_id: Optional[str] = None
    agent_role: Optional[str] = None
    metadata: dict


class ExecutionLogResponse(BaseModel):
    task_id: str
    items: list[ExecutionLogEntryResponse]
    total: int
