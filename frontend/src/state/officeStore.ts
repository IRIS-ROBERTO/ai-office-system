import { create } from 'zustand';
import { getAgentProfile } from '../data/agentProfiles';
import {
  DESK_POSITIONS,
  getDeskPosition,
  getMeetingPosition,
  getNexusWaypoint,
  type Position,
} from '../data/agentPositions';

export type TaskStatus =
  | 'queued'
  | 'pending'
  | 'assigned'
  | 'running'
  | 'in_progress'
  | 'validation'
  | 'completed'
  | 'done'
  | 'failed'
  | 'blocked';

export type TaskStage = 'input' | 'processing' | 'validation' | 'output';

export type TaskBucket = 'queue' | 'running' | 'done' | 'failed' | 'blocked';

export interface TaskPipelineStep {
  key: TaskStage;
  label: string;
  status: 'pending' | 'active' | 'done' | 'blocked';
  agent_id: string | null;
}

export interface Task {
  task_id: string;
  team: string;
  status: TaskStatus;
  request: string;
  input?: string;
  output?: string;
  validation?: string;
  priority: number;
  sla_seconds: number;
  created_at: number;
  started_at: number | null;
  completed_at: number | null;
  failed_at: number | null;
  updated_at: number;
  stage: TaskStage;
  progress: number;
  wait_seconds: number;
  dependencies: string[];
  blockers: string[];
  pipeline: TaskPipelineStep[];
  assigned_agent_id: string | null;
  assigned_agent_ids: string[];
  last_event_type?: string;
}

export interface Agent {
  agent_id: string;
  agent_name: string;
  agent_role: string;
  team: 'dev' | 'marketing' | 'orchestrator';
  status: 'idle' | 'thinking' | 'working' | 'moving';
  pose: 'seated' | 'walking' | 'standing';
  current_task_id: string | null;
  position: { x: number; y: number };
  color: string;
  completed_tasks: number;
  error_count: number;
  task_note?: string;
  task_eta_seconds?: number;
  task_dependencies?: string[];
  task_stage?: TaskStage;
  task_summary?: string;
  last_signal?: string;
}

export interface AnimationQueueItem {
  event_type: string;
  agent_id: string;
  payload: Record<string, unknown>;
  timestamp: number;
}

export interface AgentActivityItem {
  id: string;
  event_type: string;
  message: string;
  timestamp: number;
  task_id: string | null;
  tone: string;
}

export interface AgentBootstrapRecord {
  agent_id: string;
  role: string;
  team: 'dev' | 'marketing' | 'orchestrator';
  status: Agent['status'];
  current_task_id: string | null;
  completed_tasks: number;
  error_count?: number;
  position?: { x: number; y: number };
}

interface OfficeStore {
  agents: Record<string, Agent>;
  tasks: Record<string, Task>;
  animationQueue: AnimationQueueItem[];
  agentActivity: Record<string, AgentActivityItem[]>;
  connected: boolean;
  processEvent: (event: Record<string, unknown>) => void;
  hydrateAgents: (records: AgentBootstrapRecord[]) => void;
  setConnected: (v: boolean) => void;
  dequeueAnimation: () => AnimationQueueItem | undefined;
  getAgentsByTeam: (team: string) => Agent[];
  setAgentPosition: (agentId: string, position: Position) => void;
  wanderIdleAgents: () => void;
}

const ROLE_COLORS: Record<string, string> = {
  planner: '#3b82f6',
  frontend: '#22c55e',
  backend: '#ef4444',
  qa: '#a855f7',
  security: '#f59e0b',
  docs: '#06b6d4',
  research: '#10b981',
  strategy: '#6366f1',
  content: '#ec4899',
  seo: '#84cc16',
  social: '#8b5cf6',
  analytics: '#14b8a6',
  orchestrator: '#fbbf24',
  manager: '#fbbf24',
};

const TASK_STAGE_ORDER: TaskStage[] = ['input', 'processing', 'validation', 'output'];

const TASK_STATUS_BUCKET: Record<TaskStatus, TaskBucket> = {
  queued: 'queue',
  pending: 'queue',
  assigned: 'running',
  running: 'running',
  in_progress: 'running',
  validation: 'running',
  completed: 'done',
  done: 'done',
  failed: 'failed',
  blocked: 'blocked',
};

const DEV_ZONE = { xMin: 50, xMax: 590, yMin: 100, yMax: 650 };
const MARKETING_ZONE = { xMin: 780, xMax: 1390, yMin: 100, yMax: 650 };
const ORCHESTRATOR_ZONE = { x: 690, yMin: 150, yMax: 600 };

let agentIndexByTeam: Record<string, number> = { dev: 0, marketing: 0, orchestrator: 0 };

function nowMs() {
  return Date.now();
}

function getRoleColor(role: string): string {
  const lowerRole = role.toLowerCase();
  for (const [key, color] of Object.entries(ROLE_COLORS)) {
    if (lowerRole.includes(key)) return color;
  }
  return '#94a3b8';
}

export function normalizeTaskStatus(value: unknown, fallback: TaskStatus = 'queued'): TaskStatus {
  const status = String(value || '').toLowerCase();
  if (
    status === 'queued' ||
    status === 'pending' ||
    status === 'assigned' ||
    status === 'running' ||
    status === 'in_progress' ||
    status === 'validation' ||
    status === 'completed' ||
    status === 'done' ||
    status === 'failed' ||
    status === 'blocked'
  ) {
    return status;
  }
  return fallback;
}

export function getTaskBucket(status: TaskStatus): TaskBucket {
  return TASK_STATUS_BUCKET[status] ?? 'queue';
}

export function getTaskStage(status: TaskStatus, fallback: TaskStage = 'input'): TaskStage {
  if (status === 'queued' || status === 'pending') return 'input';
  if (status === 'assigned' || status === 'running' || status === 'in_progress') return 'processing';
  if (status === 'validation') return 'validation';
  if (status === 'completed' || status === 'done' || status === 'failed') return 'output';
  return fallback;
}

export function getAgentZone(agent: Agent): 'dev-zone' | 'mind-zone' | 'creative-lab' | 'boardroom' | 'lounge' {
  if (agent.status === 'moving') return 'boardroom';
  if (agent.team === 'orchestrator') return 'mind-zone';
  if (agent.status === 'idle') return 'lounge';
  if (agent.team === 'dev') return agent.status === 'thinking' ? 'mind-zone' : 'dev-zone';
  return agent.status === 'thinking' ? 'mind-zone' : 'creative-lab';
}

function getDefaultTaskPriority(team: string): number {
  if (team === 'orchestrator') return 5;
  if (team === 'dev') return 4;
  return 3;
}

function buildTaskPipeline(task: Task): TaskPipelineStep[] {
  const activeStage = task.stage || getTaskStage(task.status);
  const bucket = getTaskBucket(task.status);
  const blockedIndex = bucket === 'blocked' ? TASK_STAGE_ORDER.indexOf(activeStage) : -1;

  return TASK_STAGE_ORDER.map((stage, index) => {
    let status: TaskPipelineStep['status'] = 'pending';
    if (bucket === 'done') {
      status = 'done';
    } else if (bucket === 'failed' && index < 2) {
      status = 'done';
    } else if (bucket === 'blocked' && index === blockedIndex) {
      status = 'blocked';
    } else if (stage === activeStage) {
      status = 'active';
    } else if (TASK_STAGE_ORDER.indexOf(activeStage) > index) {
      status = 'done';
    }

    return {
      key: stage,
      label: stage === 'input'
        ? 'Input'
        : stage === 'processing'
          ? 'Processing'
          : stage === 'validation'
            ? 'Validation'
            : 'Output',
      status,
      agent_id: task.assigned_agent_id,
    };
  });
}

function syncTask(task: Task): Task {
  const createdAt = task.created_at || nowMs();
  const updatedAt = nowMs();
  const waitSeconds = Math.max(0, Math.floor((updatedAt - createdAt) / 1000));
  const stage = task.stage || getTaskStage(task.status);
  const nextTask = {
    ...task,
    created_at: createdAt,
    updated_at: updatedAt,
    wait_seconds: waitSeconds,
    stage,
  };

  return {
    ...nextTask,
    pipeline: buildTaskPipeline(nextTask),
  };
}

function getDefaultPosition(
  team: 'dev' | 'marketing' | 'orchestrator',
  index: number,
  role = '',
): { x: number; y: number } {
  if (role) {
    const lower = role.toLowerCase();
    for (const [key, pos] of Object.entries(DESK_POSITIONS)) {
      if (lower.includes(key)) return pos;
    }
  }

  if (team === 'orchestrator') {
    return { x: ORCHESTRATOR_ZONE.x, y: ORCHESTRATOR_ZONE.yMin + index * 80 };
  }

  const zone = team === 'dev' ? DEV_ZONE : MARKETING_ZONE;
  const cols = 3;
  const col = index % cols;
  const row = Math.floor(index / cols);
  const spacingX = (zone.xMax - zone.xMin) / cols;
  const spacingY = 120;
  return {
    x: zone.xMin + col * spacingX + spacingX / 2,
    y: zone.yMin + row * spacingY + 60,
  };
}

function resolveEventTeam(event: Record<string, unknown>): 'dev' | 'marketing' | 'orchestrator' {
  const role = String(event.agent_role || event.role || '').toLowerCase();
  const rawTeam = String(event.team || 'dev').toLowerCase();

  if (role.includes('orchestrator') || role.includes('manager')) {
    return 'orchestrator';
  }
  if (rawTeam === 'marketing') return 'marketing';
  return 'dev';
}

function ensureAgent(agents: Record<string, Agent>, event: Record<string, unknown>): string | undefined {
  const agentId = (event.agent_id || event.id) as string | undefined;
  if (!agentId) return undefined;

  const role = String(event.agent_role || event.role || 'worker');
  const team = resolveEventTeam(event);
  const existing = agents[agentId];

  if (existing) return agentId;

  const idx = agentIndexByTeam[team] ?? 0;
  agentIndexByTeam[team] = idx + 1;

  agents[agentId] = {
    agent_id: agentId,
    agent_name: (event.agent_name as string | undefined) || getAgentProfile(agentId, role).codename,
    agent_role: role,
    team,
    status: 'idle',
    pose: 'seated',
    current_task_id: null,
    position: (event.position as { x: number; y: number } | undefined) || getDefaultPosition(team, idx, role),
    color: getRoleColor(role),
    completed_tasks: 0,
    error_count: 0,
  };

  return agentId;
}

function ensureTask(tasks: Record<string, Task>, event: Record<string, unknown>): string | undefined {
  const taskId = event.task_id as string | undefined;
  if (!taskId) return undefined;

  if (!tasks[taskId]) {
    const payload = (event.payload as Record<string, unknown> | undefined) || {};
    const team = String(event.team || 'dev');
    const baseCreatedAt = typeof payload.created_at === 'number' ? payload.created_at : nowMs();
    const priority =
      typeof payload.priority === 'number'
        ? payload.priority
        : typeof event.priority === 'number'
          ? Number(event.priority)
          : getDefaultTaskPriority(team);

    tasks[taskId] = syncTask({
      task_id: taskId,
      team,
      status: 'queued',
      request: String(
        event.request ||
        event.description ||
        payload.request ||
        payload.subtask_title ||
        payload.description ||
        'Task in progress'
      ),
      input: typeof payload.input === 'string' ? payload.input : undefined,
      output: typeof payload.output === 'string' ? payload.output : undefined,
      validation: typeof payload.validation === 'string' ? payload.validation : undefined,
      priority,
      sla_seconds: typeof payload.sla_seconds === 'number' ? payload.sla_seconds : 1800,
      created_at: baseCreatedAt,
      started_at: null,
      completed_at: null,
      failed_at: null,
      updated_at: baseCreatedAt,
      stage: 'input',
      progress: 0,
      wait_seconds: 0,
      dependencies: Array.isArray(payload.dependencies) ? payload.dependencies.map(String) : [],
      blockers: Array.isArray(payload.blockers) ? payload.blockers.map(String) : [],
      pipeline: [],
      assigned_agent_id: null,
      assigned_agent_ids: [],
      last_event_type: String(event.event_type || ''),
    });
  }

  return taskId;
}

function buildActivityItem(event: Record<string, unknown>): AgentActivityItem | null {
  const eventType = String(event.event_type || '');
  const taskId = (event.task_id as string | undefined) ?? null;
  const role = String(event.agent_role || event.role || 'agent');
  const payload = (event.payload as Record<string, unknown> | undefined) || {};
  const subtask = typeof payload.subtask_title === 'string' ? payload.subtask_title : null;
  const request = typeof payload.request === 'string' ? payload.request : null;
  const elapsedSeconds = typeof payload.elapsed_seconds === 'number' ? payload.elapsed_seconds : null;

  const map: Record<string, { message: string; tone: string }> = {
    agent_called: { message: `${role} was called into the workflow`, tone: '#fbbf24' },
    agent_assigned: { message: `${role} accepted a new assignment`, tone: '#6366f1' },
    agent_thinking: { message: `${role} is reasoning through the next move`, tone: '#f59e0b' },
    agent_idle: { message: `${role} returned to idle state`, tone: '#64748b' },
    agent_moving: { message: `${role} is relocating through the office`, tone: '#3b82f6' },
    task_created: { message: request || 'A new mission entered the queue', tone: '#a855f7' },
    task_started: { message: subtask || 'Execution started', tone: '#f59e0b' },
    task_in_progress: { message: subtask || 'Task execution in progress', tone: '#f59e0b' },
    task_blocked: { message: subtask || 'Task blocked by dependencies', tone: '#f97316' },
    task_heartbeat: { message: elapsedSeconds ? `${subtask || 'Task still running'} · ${elapsedSeconds}s` : (subtask || 'Task still running'), tone: '#38bdf8' },
    task_completed: { message: subtask || 'Task completed successfully', tone: '#22c55e' },
    task_failed: { message: subtask || 'Task failed and needs review', tone: '#ef4444' },
    git_commit: { message: `Commit ${String(payload.sha || '').slice(0, 8)} registered`, tone: '#22c55e' },
    git_push: { message: `Push ${String(payload.sha || '').slice(0, 8)} registered`, tone: '#00ff88' },
    commit_failed: { message: String(payload.reason || 'Commit evidence failed'), tone: '#ef4444' },
  };

  const template = map[eventType];
  if (!template) return null;

  const ts = typeof event.timestamp === 'string' ? Date.parse(event.timestamp) : nowMs();
  return {
    id: String(event.event_id || `${eventType}-${nowMs()}-${Math.random()}`),
    event_type: eventType,
    message: template.message,
    timestamp: Number.isNaN(ts) ? nowMs() : ts,
    task_id: taskId,
    tone: template.tone,
  };
}

export const useOfficeStore = create<OfficeStore>((set, get) => ({
  agents: {},
  tasks: {},
  animationQueue: [],
  agentActivity: {},
  connected: false,

  setConnected: (v) => set({ connected: v }),

  hydrateAgents: (records) => {
    set((state) => {
      const nextAgents = { ...state.agents };
      const nextActivity = { ...state.agentActivity };

      for (const record of records) {
        const team =
          record.team === 'orchestrator'
            ? 'orchestrator'
            : record.team === 'marketing'
              ? 'marketing'
              : 'dev';
        const profile = getAgentProfile(record.agent_id, record.role);
        const existing = nextAgents[record.agent_id];
        const idx = agentIndexByTeam[team] ?? 0;

        if (!existing) {
          agentIndexByTeam[team] = idx + 1;
        }

        nextAgents[record.agent_id] = {
          agent_id: record.agent_id,
          agent_name: profile.codename,
          agent_role: record.role,
          team,
          status: record.status,
          pose: (record.status === 'thinking' || record.status === 'moving') ? 'standing' : 'seated',
          current_task_id: record.current_task_id,
          position: record.position || existing?.position || getDefaultPosition(team, idx, record.role),
          color: existing?.color || getRoleColor(record.role),
          completed_tasks: record.completed_tasks,
          error_count: record.error_count ?? existing?.error_count ?? 0,
        };

        if (!nextActivity[record.agent_id]) {
          nextActivity[record.agent_id] = [
            {
              id: `${record.agent_id}-boot`,
              event_type: 'agent_bootstrapped',
              message: `${profile.codename} profile loaded into the office`,
              timestamp: nowMs(),
              task_id: null,
              tone: '#94a3b8',
            },
          ];
        }
      }

      return { agents: nextAgents, agentActivity: nextActivity };
    });
  },

  processEvent: (event) => {
    const eventType = String(event.event_type || '');

    set((state) => {
      const newAgents = { ...state.agents };
      const newTasks = { ...state.tasks };
      const newQueue = [...state.animationQueue];
      const newActivity = { ...state.agentActivity };
      const payload = (event.payload as Record<string, unknown> | undefined) || {};
      const agentId = ensureAgent(newAgents, event);
      const taskId = ensureTask(newTasks, event);
      const activityItem = buildActivityItem(event);
      const task = taskId ? newTasks[taskId] : undefined;

      switch (eventType) {
        case 'agent_registered':
        case 'agent_created':
          break;

        case 'agent_called':
        case 'agent_thinking': {
          if (agentId && newAgents[agentId]) {
            const role = newAgents[agentId].agent_role;
            const team = newAgents[agentId].team;
            const meetPos = getMeetingPosition(role) ?? newAgents[agentId].position;
            const nexusWP = getNexusWaypoint(team);

            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'moving',
              pose: 'walking',
              position: nexusWP,
              current_task_id: taskId ?? newAgents[agentId].current_task_id,
              task_summary: String(payload.subtask_title || payload.request || task?.request || 'Planning next move'),
              task_dependencies: Array.isArray(payload.dependencies) ? payload.dependencies.map(String) : task?.dependencies,
              task_stage: 'processing',
              last_signal: eventType,
            };

            const cId = agentId;
            const finalPos = meetPos;
            setTimeout(() => {
              set((s) => {
                if (!s.agents[cId]) return s;
                return {
                  agents: {
                    ...s.agents,
                    [cId]: {
                      ...s.agents[cId],
                      status: 'thinking',
                      pose: 'standing',
                      position: finalPos,
                      last_signal: eventType,
                    },
                  },
                };
              });
            }, 1800);
          }
          break;
        }

        case 'agent_idle': {
          if (agentId && newAgents[agentId]) {
            const role = newAgents[agentId].agent_role;
            const team = newAgents[agentId].team;
            const deskPos = getDeskPosition(role) ?? newAgents[agentId].position;
            const inBoardroom = newAgents[agentId].position.y > 480;

            if (inBoardroom) {
              const nexusWP = getNexusWaypoint(team);
              newAgents[agentId] = {
                ...newAgents[agentId],
                status: 'moving',
                pose: 'walking',
                position: nexusWP,
                current_task_id: null,
                task_stage: 'input',
                last_signal: eventType,
              };
              const cId = agentId;
              const finalPos = deskPos;
              setTimeout(() => {
                set((s) => {
                  if (!s.agents[cId]) return s;
                  return {
                    agents: {
                      ...s.agents,
                      [cId]: {
                        ...s.agents[cId],
                        status: 'idle',
                        pose: 'seated',
                        position: finalPos,
                        last_signal: eventType,
                      },
                    },
                  };
                });
              }, 1800);
            } else {
              newAgents[agentId] = {
                ...newAgents[agentId],
                status: 'idle',
                pose: 'seated',
                position: deskPos,
                current_task_id: null,
                task_stage: 'input',
                task_summary: 'Monitoring backlog and historical signals',
                last_signal: eventType,
              };
            }
          }
          break;
        }

        case 'agent_status_changed':
        case 'agent_updated': {
          if (agentId && newAgents[agentId]) {
            const newStatus = normalizeTaskStatus(event.status as TaskStatus | string | undefined, 'queued');
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: (event.status as Agent['status']) || newAgents[agentId].status,
              current_task_id: (event.task_id as string | null) ?? newAgents[agentId].current_task_id,
              task_stage: getTaskStage(newStatus),
              last_signal: eventType,
            };
          }
          break;
        }

        case 'agent_moving':
        case 'agent_moved': {
          if (agentId && newAgents[agentId]) {
            const pos = event.position as { x: number; y: number };
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'moving',
              position: pos || newAgents[agentId].position,
              last_signal: eventType,
            };
          }
          break;
        }

        case 'task_created': {
          if (taskId && newTasks[taskId]) {
            newTasks[taskId] = syncTask({
              ...newTasks[taskId],
              status: 'queued',
              stage: 'input',
              request: String(event.request || event.description || newTasks[taskId].request),
              priority: typeof payload.priority === 'number' ? payload.priority : newTasks[taskId].priority,
              input: typeof payload.input === 'string' ? payload.input : newTasks[taskId].input,
              dependencies: Array.isArray(payload.dependencies) ? payload.dependencies.map(String) : newTasks[taskId].dependencies,
              blockers: Array.isArray(payload.blockers) ? payload.blockers.map(String) : newTasks[taskId].blockers,
              assigned_agent_ids: newTasks[taskId].assigned_agent_ids,
              assigned_agent_id: newTasks[taskId].assigned_agent_id,
              last_event_type: eventType,
            });
          }
          break;
        }

        case 'agent_assigned':
        case 'task_assigned': {
          if (taskId && newTasks[taskId]) {
            newTasks[taskId] = syncTask({
              ...newTasks[taskId],
              status: 'assigned',
              stage: 'processing',
              request: String(payload.subtask_title || newTasks[taskId].request),
              assigned_agent_id: agentId || null,
              assigned_agent_ids: agentId ? Array.from(new Set([...newTasks[taskId].assigned_agent_ids, agentId])) : newTasks[taskId].assigned_agent_ids,
              updated_at: nowMs(),
              last_event_type: eventType,
            });
          }
          if (agentId && newAgents[agentId]) {
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'working',
              current_task_id: taskId ?? newAgents[agentId].current_task_id,
              task_stage: 'processing',
              task_summary: String(payload.subtask_title || task?.request || newAgents[agentId].task_summary || 'Working assignment'),
              last_signal: eventType,
            };
          }
          break;
        }

        case 'task_started':
        case 'task_in_progress': {
          if (taskId && newTasks[taskId]) {
            newTasks[taskId] = syncTask({
              ...newTasks[taskId],
              status: 'running',
              stage: 'processing',
              request: String(payload.subtask_title || payload.description || newTasks[taskId].request),
              started_at: newTasks[taskId].started_at || nowMs(),
              updated_at: nowMs(),
              progress: Math.max(newTasks[taskId].progress, 35),
              last_event_type: eventType,
            });
          }
          if (agentId && newAgents[agentId]) {
            const role = newAgents[agentId].agent_role;
            const team = newAgents[agentId].team;
            const deskPos = getDeskPosition(role) ?? newAgents[agentId].position;
            const inBoardroom = newAgents[agentId].position.y > 480;

            if (inBoardroom) {
              const nexusWP = getNexusWaypoint(team);
              newAgents[agentId] = {
                ...newAgents[agentId],
                status: 'moving',
                pose: 'walking',
                position: nexusWP,
                current_task_id: taskId ?? newAgents[agentId].current_task_id,
                task_stage: 'processing',
                last_signal: eventType,
              };
              const cId = agentId;
              const finalPos = deskPos;
              const finalTaskId = taskId;
              setTimeout(() => {
                set((s) => {
                  if (!s.agents[cId]) return s;
                  return {
                    agents: {
                      ...s.agents,
                      [cId]: {
                        ...s.agents[cId],
                        status: 'working',
                        pose: 'seated',
                        position: finalPos,
                        current_task_id: finalTaskId ?? s.agents[cId].current_task_id,
                        task_stage: 'processing',
                        last_signal: eventType,
                      },
                    },
                  };
                });
              }, 1800);
            } else {
              newAgents[agentId] = {
                ...newAgents[agentId],
                status: 'working',
                pose: 'seated',
                position: deskPos,
                current_task_id: taskId ?? newAgents[agentId].current_task_id,
                task_stage: 'processing',
                last_signal: eventType,
              };
            }
          }
          break;
        }

        case 'task_completed': {
          const isFinalTaskEvent =
            typeof payload.output_length === 'number' ||
            typeof payload.subtask_count === 'number';

          if (taskId && newTasks[taskId]) {
            newTasks[taskId] = syncTask({
              ...newTasks[taskId],
              status: isFinalTaskEvent ? 'completed' : 'running',
              stage: isFinalTaskEvent ? 'output' : 'validation',
              progress: isFinalTaskEvent ? 100 : Math.max(newTasks[taskId].progress, 70),
              completed_at: isFinalTaskEvent ? nowMs() : newTasks[taskId].completed_at,
              output: typeof payload.output === 'string' ? payload.output : newTasks[taskId].output,
              validation: typeof payload.validation === 'string' ? payload.validation : newTasks[taskId].validation,
              last_event_type: eventType,
            });
          }
          if (agentId && newAgents[agentId]) {
            const role = newAgents[agentId].agent_role;
            const deskPos = getDeskPosition(role) ?? newAgents[agentId].position;
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: isFinalTaskEvent ? 'idle' : newAgents[agentId].status,
              pose: isFinalTaskEvent ? 'seated' : newAgents[agentId].pose,
              position: isFinalTaskEvent ? deskPos : newAgents[agentId].position,
              current_task_id: isFinalTaskEvent ? null : newAgents[agentId].current_task_id,
              completed_tasks: isFinalTaskEvent ? newAgents[agentId].completed_tasks + 1 : newAgents[agentId].completed_tasks,
              task_stage: isFinalTaskEvent ? 'input' : 'validation',
              task_summary: isFinalTaskEvent ? 'Returned to lounge after validation' : newAgents[agentId].task_summary,
              last_signal: eventType,
            };
          }
          break;
        }

        case 'task_failed': {
          if (taskId && newTasks[taskId]) {
            newTasks[taskId] = syncTask({
              ...newTasks[taskId],
              status: 'failed',
              stage: 'output',
              failed_at: nowMs(),
              progress: Math.min(newTasks[taskId].progress, 60),
              last_event_type: eventType,
            });
          }
          if (agentId && newAgents[agentId]) {
            const role = newAgents[agentId].agent_role;
            const deskPos = getDeskPosition(role) ?? newAgents[agentId].position;
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'idle',
              pose: 'seated',
              position: deskPos,
              current_task_id: null,
              error_count: newAgents[agentId].error_count + 1,
              task_stage: 'input',
              task_summary: 'Recovered to idle after failure',
              last_signal: eventType,
            };
          }
          break;
        }

        case 'task_blocked': {
          if (taskId && newTasks[taskId]) {
            newTasks[taskId] = syncTask({
              ...newTasks[taskId],
              status: 'blocked',
              stage: 'validation',
              blockers: Array.isArray(payload.blockers) ? payload.blockers.map(String) : newTasks[taskId].blockers,
              last_event_type: eventType,
            });
          }
          if (agentId && newAgents[agentId]) {
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'thinking',
              task_note: String(payload.reason || 'Waiting on dependencies'),
              task_stage: 'validation',
              last_signal: eventType,
            };
          }
          break;
        }

        default:
          break;
      }

      if (agentId) {
        newQueue.push({
          event_type: eventType,
          agent_id: agentId,
          payload: event,
          timestamp: nowMs() + 500,
        });

        if (activityItem) {
          const current = newActivity[agentId] || [];
          newActivity[agentId] = [activityItem, ...current].slice(0, 12);
        }
      }

      for (const [id, taskRecord] of Object.entries(newTasks)) {
        newTasks[id] = syncTask(taskRecord);
      }

      return {
        agents: newAgents,
        tasks: newTasks,
        animationQueue: newQueue,
        agentActivity: newActivity,
      };
    });
  },

  dequeueAnimation: () => {
    const { animationQueue } = get();
    const now = nowMs();
    const readyIndex = animationQueue.findIndex((item) => item.timestamp <= now);
    if (readyIndex === -1) return undefined;
    const item = animationQueue[readyIndex];
    set({ animationQueue: animationQueue.filter((_, i) => i !== readyIndex) });
    return item;
  },

  getAgentsByTeam: (team) => {
    const { agents } = get();
    return Object.values(agents).filter((a) => a.team === team);
  },

  setAgentPosition: (agentId, position) => {
    set((state) => {
      const agent = state.agents[agentId];
      if (!agent) return state;
      return {
        agents: {
          ...state.agents,
          [agentId]: { ...agent, status: 'moving', position, last_signal: 'agent_moved' },
        },
      };
    });
  },

  wanderIdleAgents: () => {
    set((state) => {
      const updated: Record<string, Agent> = {};
      for (const [id, agent] of Object.entries(state.agents)) {
        if (agent.status !== 'idle' || agent.pose !== 'seated') continue;
        if (Math.random() > 0.25) continue;
        const base = getDeskPosition(agent.agent_role) ?? agent.position;
        updated[id] = {
          ...agent,
          position: {
            x: base.x + (Math.random() - 0.5) * 8,
            y: base.y + (Math.random() - 0.5) * 4,
          },
        };
      }
      if (Object.keys(updated).length === 0) return state;
      return { agents: { ...state.agents, ...updated } };
    });
  },
}));
