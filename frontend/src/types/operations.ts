export type TeamName = 'dev' | 'marketing' | 'orchestrator';

export interface ServiceRequest {
  request_id: string;
  title: string;
  team: 'dev' | 'marketing';
  status: string;
  stage_label: string;
  requester_name?: string | null;
  requester_team?: string | null;
  urgency: string;
  priority: number;
  desired_due_date?: string | null;
  acceptance_criteria?: string | null;
  request: string;
  task_id?: string | null;
  current_agent_role?: string | null;
  tested_by_team: boolean;
  approved_by_orchestrator: boolean;
  last_execution_message?: string | null;
  last_execution_stage?: string | null;
  execution_log_size: number;
  created_at: string;
  updated_at: string;
}

export interface ServiceRequestListResponse {
  items: ServiceRequest[];
  total: number;
}

export interface ExecutionLogItem {
  timestamp: string;
  stage: string;
  message: string;
  level: string;
  team: string;
  task_id: string;
  agent_id?: string | null;
  agent_role?: string | null;
  metadata: Record<string, unknown>;
}

export interface ExecutionLogResponse {
  task_id: string;
  items: ExecutionLogItem[];
  total: number;
}

export interface SystemHealth {
  api: string;
  redis: string;
  event_bus?: string;
  event_bus_persistent?: boolean;
  ollama: string;
  available_models: string[];
  active_tasks: number;
}

export interface AgentPersonalityConfig {
  agent_id: string;
  role: string;
  team: string;
  persona_name: string;
  mission: string;
  personality: string[];
  operating_rules: string[];
  autonomy_level: string;
  model_policy: string;
  visibility_level: string;
  updated_at?: string | null;
}

export interface DeliveryLedgerAgent {
  agent_key: string;
  agent_id: string;
  agent_role: string;
  team: string;
  total_deliveries: number;
  approved_deliveries: number;
  failed_deliveries: number;
  functional_ready: number;
  pushed_to_github: number;
  commit_ready: number;
  approval_rate: number;
  functional_rate: number;
  github_push_rate: number;
  commit_traceability_rate: number;
  premium_score: number;
  maturity_level: string;
  next_actions: string[];
}

export interface DeliveryLedgerTeam {
  team: string;
  agents: number;
  total_deliveries: number;
  approval_rate: number;
  functional_rate: number;
  github_push_rate: number;
  commit_traceability_rate: number;
  premium_score: number;
}

export interface DeliveryLedger {
  total_deliveries: number;
  approved_deliveries: number;
  functional_ready: number;
  pushed_to_github: number;
  agents: DeliveryLedgerAgent[];
  teams: DeliveryLedgerTeam[];
  recommendations: string[];
}

export interface AgentAutonomyPolicy {
  agent_id: string;
  agent_role: string;
  team: string;
  eligible_for_autonomous: boolean;
  maturity_level: string;
  premium_score: number;
  total_deliveries?: number;
  approval_rate?: number;
  functional_rate?: number;
  github_push_rate?: number;
  commit_traceability_rate?: number;
  blockers: string[];
  next_actions: string[];
}

export type PipelineState = 'pending' | 'active' | 'completed' | 'failed';
export type SlaState = 'healthy' | 'warning' | 'breached';

export interface TaskStage {
  id: 'input' | 'processing' | 'validation' | 'output';
  label: string;
  owner: string;
  state: PipelineState;
  detail: string;
}

export interface OfficeTask {
  requestId: string;
  taskId: string | null;
  title: string;
  team: 'dev' | 'marketing';
  status: string;
  stageLabel: string;
  request: string;
  priority: number;
  urgency: string;
  createdAt: string;
  updatedAt: string;
  desiredDueDate?: string | null;
  currentAgentRole?: string | null;
  testedByTeam: boolean;
  approvedByOrchestrator: boolean;
  lastExecutionMessage?: string | null;
  lastExecutionStage?: string | null;
  executionLogSize: number;
  queueMinutes: number;
  slaState: SlaState;
  stages: TaskStage[];
  involvedRoles: string[];
  bottlenecks: string[];
}
