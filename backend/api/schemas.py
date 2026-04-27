"""
AI Office System — API Schemas
Pydantic models para request/response da API REST e WebSocket.
"""
from pydantic import BaseModel, Field
from typing import Optional


class TaskRequest(BaseModel):
    request: str = Field(..., min_length=10, max_length=10000)
    priority: int = Field(default=1, ge=1, le=4)


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
    autonomy: str = ""
    segmentation: str = ""
    declared_tools: list[str] = Field(default_factory=list)
    memory_posture: str = ""
    tool_policy: dict
    brain_profile: dict = Field(default_factory=dict)
    picoclaw: dict
    access_policy: dict = Field(default_factory=dict)
    upgrade_track: list[str] = Field(default_factory=list)


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


class MemoryCreateRequest(BaseModel):
    memory_class: str
    content: str
    source: str = "operator_manual"
    source_id: str = ""
    task_id: str = ""
    subtask_id: str = ""
    agent_id: str = ""
    agent_role: str = ""
    project_path: str = ""
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.8
    approved: bool = True
    metadata: dict = Field(default_factory=dict)


class CapabilityAccessCreate(BaseModel):
    agent_id: str = Field(..., min_length=2, max_length=120)
    agent_role: str = Field(default="", max_length=80)
    task_id: str = Field(default="", max_length=120)
    resource_type: str = Field(..., pattern="^(web|directory|screen)$")
    resource: str = Field(..., min_length=1, max_length=1000)
    access_level: str = Field(..., pattern="^(read|write|execute|control)$")
    reason: str = Field(..., min_length=10, max_length=2000)
    duration_minutes: int = Field(default=60, ge=1, le=240)


class CapabilityAccessDecision(BaseModel):
    operator: str = Field(default="operator", max_length=120)
    reason: str = Field(default="", max_length=1000)


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
    runtime_gateway: dict = Field(default_factory=dict)
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
    title: str = Field(..., min_length=3, max_length=200)
    team: str = Field(..., pattern="^(dev|marketing|Dev|Marketing|DEV|MARKETING)$")
    request: str = Field(..., min_length=10, max_length=10000)
    requester_name: Optional[str] = Field(default=None, max_length=100)
    requester_team: Optional[str] = Field(default=None, max_length=100)
    urgency: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    desired_due_date: Optional[str] = Field(default=None, max_length=30)
    acceptance_criteria: Optional[str] = Field(default=None, max_length=5000)


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


# ---------------------------------------------------------------------------
# Research / Intel schemas
# ---------------------------------------------------------------------------

class ResearchFinding(BaseModel):
    id: str
    source: str = "combination"
    name: str = ""
    title: str
    description: str = ""
    url: str = ""
    language: str = "N/A"
    license: str = "N/A"
    score: int
    grade: str
    grade_label: str
    breakdown: dict = Field(default_factory=dict)
    iris_fit: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    stars: int = 0
    forks: int = 0
    downloads: int = 0
    likes: int = 0
    pipeline_tag: str = ""
    created_at: str = ""
    updated_at: str = ""
    pushed_at: str = ""
    scraped_at: str = ""
    query_used: str = ""
    # Campos específicos de combinação
    type: str = "project"
    projects: list[str] = Field(default_factory=list)
    project_names: list[str] = Field(default_factory=list)
    combination_rationale: str = ""


class ResearchFindingsResponse(BaseModel):
    total: int
    returned: int
    items: list[ResearchFinding]
    last_updated: Optional[str] = None


class ResearchStatsResponse(BaseModel):
    total: int
    by_source: dict
    by_grade: dict
    avg_score: float
    top_finding: Optional[dict] = None


class ResearchScheduleConfig(BaseModel):
    enabled: bool = True
    github_enabled: bool = True
    gitlab_enabled: bool = True
    huggingface_enabled: bool = True
    interval_hours: int = 6
    scrape_time: str = "08:00"
    github_queries: list[str] = Field(default_factory=list)
    gitlab_queries: list[str] = Field(default_factory=list)
    hf_queries: list[str] = Field(default_factory=list)
    min_stars_github: int = 50
    min_stars_gitlab: int = 25
    days_back: int = 30
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    total_runs: int = 0


class ResearchScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    github_enabled: Optional[bool] = None
    gitlab_enabled: Optional[bool] = None
    huggingface_enabled: Optional[bool] = None
    interval_hours: Optional[int] = None
    scrape_time: Optional[str] = None
    github_queries: Optional[list[str]] = None
    gitlab_queries: Optional[list[str]] = None
    hf_queries: Optional[list[str]] = None
    min_stars_github: Optional[int] = None
    min_stars_gitlab: Optional[int] = None
    days_back: Optional[int] = None


class ResearchScrapeResponse(BaseModel):
    status: str
    message: str = ""
    started_at: str = ""
    completed_at: str = ""
    new_findings: int = 0
    total_findings: int = 0
    error: str = ""
