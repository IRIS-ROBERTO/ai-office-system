import type { OfficeTask, PipelineState, ServiceRequest, SlaState, TaskStage } from '../types/operations';

const SLA_HOURS: Record<string, number> = {
  critical: 1,
  high: 4,
  medium: 8,
  low: 24,
};

const TEAM_ROLE_MAP: Record<'dev' | 'marketing', string[]> = {
  dev: ['planner', 'backend', 'frontend', 'qa', 'security', 'docs', 'orchestrator'],
  marketing: ['research', 'strategy', 'content', 'seo', 'social', 'analytics', 'orchestrator'],
};

function getElapsedMinutes(from: string): number {
  const startedAt = new Date(from).getTime();
  if (Number.isNaN(startedAt)) return 0;
  return Math.max(0, Math.round((Date.now() - startedAt) / 60000));
}

function getSlaState(record: ServiceRequest, queueMinutes: number): SlaState {
  if (record.status === 'completed') return 'healthy';

  const limitHours = SLA_HOURS[record.urgency] ?? 8;
  const limitMinutes = limitHours * 60;

  if (queueMinutes >= limitMinutes) return 'breached';
  if (queueMinutes >= limitMinutes * 0.7) return 'warning';
  return 'healthy';
}

function stageState(record: ServiceRequest, stage: TaskStage['id']): PipelineState {
  const status = record.status;

  if (status === 'changes_requested' || status === 'failed') {
    if (stage === 'validation') return 'failed';
    if (stage === 'input' || stage === 'processing') return 'completed';
    return 'pending';
  }

  if (status === 'completed') return 'completed';
  if (status === 'awaiting_approval') {
    if (stage === 'output') return 'active';
    return stage === 'input' || stage === 'processing' || stage === 'validation'
      ? 'completed'
      : 'pending';
  }
  if (status === 'in_testing') {
    if (stage === 'validation') return 'active';
    return stage === 'input' || stage === 'processing' ? 'completed' : 'pending';
  }
  if (status === 'planned' || status === 'in_execution' || status === 'triage') {
    if (stage === 'input' && status === 'triage') return 'active';
    if (stage === 'processing') return 'active';
    return stage === 'input' ? 'completed' : 'pending';
  }
  if (status === 'received') {
    return stage === 'input' ? 'active' : 'pending';
  }
  return stage === 'input' ? 'active' : 'pending';
}

function buildStages(record: ServiceRequest): TaskStage[] {
  return [
    {
      id: 'input',
      label: 'Input',
      owner: 'CROWN',
      state: stageState(record, 'input'),
      detail: 'Triagem, prioridade e contexto operacional.',
    },
    {
      id: 'processing',
      label: 'Processing',
      owner: (record.current_agent_role ?? 'squad').toUpperCase(),
      state: stageState(record, 'processing'),
      detail: record.last_execution_message ?? 'Execução distribuída entre agentes responsáveis.',
    },
    {
      id: 'validation',
      label: 'Validation',
      owner: record.tested_by_team ? 'QA' : 'Quality Gate',
      state: stageState(record, 'validation'),
      detail: record.tested_by_team
        ? 'Validação do time concluída.'
        : 'Aguardando testes, revisão ou aprovação intermediária.',
    },
    {
      id: 'output',
      label: 'Output',
      owner: 'CROWN',
      state: stageState(record, 'output'),
      detail: record.approved_by_orchestrator
        ? 'Entrega aprovada e encerrada pelo orquestrador.'
        : 'Saída final aguardando aprovação e fechamento.',
    },
  ];
}

function buildBottlenecks(record: ServiceRequest, queueMinutes: number, slaState: SlaState): string[] {
  const issues: string[] = [];

  if (record.status === 'changes_requested') {
    issues.push('Validação falhou e devolveu a tarefa para nova rodada.');
  }
  if (!record.tested_by_team && record.team === 'dev' && record.status !== 'triage') {
    issues.push('Entrega sem evidência de teste do time.');
  }
  if (slaState === 'breached') {
    issues.push(`SLA ultrapassado após ${queueMinutes} min em fila/operação.`);
  }
  if (record.status === 'awaiting_approval') {
    issues.push('Aguardando decisão final do orquestrador.');
  }
  if (record.last_execution_stage === 'runtime_error') {
    issues.push('Runtime reportou falha na última execução.');
  }

  return issues;
}

export function normalizeServiceRequest(record: ServiceRequest): OfficeTask {
  const queueMinutes = getElapsedMinutes(record.created_at);
  const slaState = getSlaState(record, queueMinutes);
  const involvedRoles = Array.from(
    new Set([
      ...TEAM_ROLE_MAP[record.team],
      ...(record.current_agent_role ? [record.current_agent_role] : []),
      ...(record.approved_by_orchestrator ? ['orchestrator'] : []),
    ]),
  );

  return {
    requestId: record.request_id,
    taskId: record.task_id ?? null,
    title: record.title,
    team: record.team,
    status: record.status,
    stageLabel: record.stage_label,
    request: record.request,
    priority: record.priority,
    urgency: record.urgency,
    createdAt: record.created_at,
    updatedAt: record.updated_at,
    desiredDueDate: record.desired_due_date,
    currentAgentRole: record.current_agent_role ?? null,
    testedByTeam: record.tested_by_team,
    approvedByOrchestrator: record.approved_by_orchestrator,
    lastExecutionMessage: record.last_execution_message ?? null,
    lastExecutionStage: record.last_execution_stage ?? null,
    executionLogSize: record.execution_log_size,
    queueMinutes,
    slaState,
    stages: buildStages(record),
    involvedRoles,
    bottlenecks: buildBottlenecks(record, queueMinutes, slaState),
  };
}

export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes === 0 ? `${hours} h` : `${hours} h ${remainingMinutes} min`;
}

export function formatDateLabel(value?: string | null): string {
  if (!value) return 'Sem prazo';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
