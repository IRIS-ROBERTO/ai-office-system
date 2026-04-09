import { create } from 'zustand';
import { getAgentProfile } from '../data/agentProfiles';
import {
  DESK_POSITIONS,
  getDeskPosition,
  getMeetingPosition,
  getNexusWaypoint,
  type Position,
} from '../data/agentPositions';

export interface Agent {
  agent_id: string;
  agent_name: string;        // Codinome: ATLAS, PIXEL, FORGE, etc.
  agent_role: string;
  team: 'dev' | 'marketing' | 'orchestrator';
  status: 'idle' | 'thinking' | 'working' | 'moving';
  /** Visual body pose — drives seated vs walking vs standing rendering in AgentSprite. */
  pose: 'seated' | 'walking' | 'standing';
  current_task_id: string | null;
  position: { x: number; y: number };
  color: string;
  completed_tasks: number;
  error_count: number;
}

export interface Task {
  task_id: string;
  team: string;
  status: string;
  request: string;
  assigned_agent_id: string | null;
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

  // Actions
  processEvent: (event: Record<string, unknown>) => void;
  hydrateAgents: (records: AgentBootstrapRecord[]) => void;
  setConnected: (v: boolean) => void;
  dequeueAnimation: () => AnimationQueueItem | undefined;
  getAgentsByTeam: (team: string) => Agent[];
  /** Teleport an agent to a new target position (AgentSprite lerps smoothly). */
  setAgentPosition: (agentId: string, position: Position) => void;
  /** Trigger autonomous idle wander (call from external timer). */
  wanderIdleAgents: () => void;
}

const ROLE_COLORS: Record<string, string> = {
  // Dev team — tons frios
  planner:    '#3b82f6',   // blue  — ATLAS
  frontend:   '#22c55e',   // green — PIXEL
  backend:    '#ef4444',   // red   — FORGE
  qa:         '#a855f7',   // purple — SHERLOCK
  security:   '#f59e0b',   // amber — AEGIS
  docs:       '#06b6d4',   // cyan  — LORE
  // Marketing team — tons quentes/vibrantes
  research:   '#10b981',   // emerald — ORACLE
  strategy:   '#6366f1',   // indigo  — MAVEN
  content:    '#ec4899',   // pink    — NOVA
  seo:        '#84cc16',   // lime    — APEX
  social:     '#8b5cf6',   // violet  — PULSE
  analytics:  '#14b8a6',   // teal    — PRISM
  // Orchestrators
  orchestrator: '#fbbf24', // yellow
  manager:      '#fbbf24',
};

// Default positions — matches new 1440x810 canvas layout
// Dev zone: 0–636, Corridor: 636–744, Marketing: 744–1440
const DEV_ZONE      = { xMin: 50,  xMax: 590,  yMin: 100, yMax: 650 };
const MARKETING_ZONE= { xMin: 780, xMax: 1390, yMin: 100, yMax: 650 };
const ORCHESTRATOR_ZONE = { x: 690, yMin: 150, yMax: 600 };

function getRoleColor(role: string): string {
  const lowerRole = role.toLowerCase();
  for (const [key, color] of Object.entries(ROLE_COLORS)) {
    if (lowerRole.includes(key)) return color;
  }
  return '#94a3b8'; // slate default
}

function getDefaultPosition(
  team: 'dev' | 'marketing' | 'orchestrator',
  index: number,
  role = '',
): { x: number; y: number } {
  // Try to match by role against canonical desk positions first
  if (role) {
    const lower = role.toLowerCase();
    for (const [key, pos] of Object.entries(DESK_POSITIONS)) {
      if (lower.includes(key)) return pos;
    }
  }
  // Fallback: orchestrator corridor
  if (team === 'orchestrator') {
    return { x: ORCHESTRATOR_ZONE.x, y: ORCHESTRATOR_ZONE.yMin + index * 80 };
  }
  // Fallback: zone grid
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

let agentIndexByTeam: Record<string, number> = { dev: 0, marketing: 0, orchestrator: 0 };

function resolveEventTeam(event: Record<string, unknown>): 'dev' | 'marketing' | 'orchestrator' {
  const role = String(event.agent_role || event.role || '').toLowerCase();
  const rawTeam = String(event.team || 'dev').toLowerCase();

  if (role.includes('orchestrator') || role.includes('manager')) {
    return 'orchestrator';
  }
  if (rawTeam === 'marketing') {
    return 'marketing';
  }
  return 'dev';
}

function ensureAgent(
  agents: Record<string, Agent>,
  event: Record<string, unknown>
): string | undefined {
  const agentId = (event.agent_id || event.id) as string | undefined;
  if (!agentId) return undefined;

  const role = String(event.agent_role || event.role || 'worker');
  const effectiveTeam = resolveEventTeam(event);
  const existing = agents[agentId];

  if (existing) {
    return agentId;
  }

  const idx = agentIndexByTeam[effectiveTeam] ?? 0;
  agentIndexByTeam[effectiveTeam] = idx + 1;

  agents[agentId] = {
    agent_id: agentId,
    agent_name:
      (event.agent_name as string | undefined) ||
      getAgentProfile(agentId, role).codename,
    agent_role: role,
    team: effectiveTeam,
    status: 'idle',
    pose: 'seated',
    current_task_id: null,
    position:
      (event.position as { x: number; y: number } | undefined) ||
      getDefaultPosition(effectiveTeam, idx, role),
    color: getRoleColor(role),
    completed_tasks: 0,
    error_count: 0,
  };

  return agentId;
}

function ensureTask(
  tasks: Record<string, Task>,
  event: Record<string, unknown>
): string | undefined {
  const taskId = event.task_id as string | undefined;
  if (!taskId) return undefined;

  if (!tasks[taskId]) {
    const payload = (event.payload as Record<string, unknown> | undefined) || {};
    tasks[taskId] = {
      task_id: taskId,
      team: String(event.team || 'dev'),
      status: 'pending',
      request: String(
        event.request ||
        event.description ||
        payload.request ||
        payload.subtask_title ||
        payload.description ||
        'Task in progress'
      ),
      assigned_agent_id: null,
    };
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

  const map: Record<string, { message: string; tone: string }> = {
    agent_called: { message: `${role} was called into the workflow`, tone: '#fbbf24' },
    agent_assigned: { message: `${role} accepted a new assignment`, tone: '#6366f1' },
    agent_thinking: { message: `${role} is reasoning through the next move`, tone: '#f59e0b' },
    agent_idle: { message: `${role} returned to idle state`, tone: '#64748b' },
    agent_moving: { message: `${role} is relocating through the office`, tone: '#3b82f6' },
    task_created: { message: request || 'A new mission entered the queue', tone: '#a855f7' },
    task_started: { message: subtask || 'Execution started', tone: '#f59e0b' },
    task_in_progress: { message: subtask || 'Task execution in progress', tone: '#f59e0b' },
    task_completed: { message: subtask || 'Task completed successfully', tone: '#22c55e' },
    task_failed: { message: subtask || 'Task failed and needs review', tone: '#ef4444' },
  };

  const template = map[eventType];
  if (!template) return null;

  const ts = typeof event.timestamp === 'string' ? Date.parse(event.timestamp) : Date.now();
  return {
    id: String(event.event_id || `${eventType}-${Date.now()}-${Math.random()}`),
    event_type: eventType,
    message: template.message,
    timestamp: Number.isNaN(ts) ? Date.now() : ts,
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
        const effectiveTeam =
          team === 'orchestrator'
            ? 'orchestrator'
            : team === 'marketing'
              ? 'marketing'
              : 'dev';
        const idx = agentIndexByTeam[effectiveTeam] ?? 0;

        if (!existing) {
          agentIndexByTeam[effectiveTeam] = idx + 1;
        }

        nextAgents[record.agent_id] = {
          agent_id: record.agent_id,
          agent_name: profile.codename,
          agent_role: record.role,
          team,
          status: record.status,
          // Agents boot seated at their desks; update if active status requires standing
          pose: (record.status === 'thinking' || record.status === 'moving')
            ? 'standing'
            : 'seated',
          current_task_id: record.current_task_id,
          position: record.position || existing?.position || getDefaultPosition(effectiveTeam, idx, record.role),
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
              timestamp: Date.now(),
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
      const agentId = ensureAgent(newAgents, event);
      const taskId = ensureTask(newTasks, event);
      const activityItem = buildActivityItem(event);

      switch (eventType) {
        case 'agent_registered':
        case 'agent_created': {
          break;
        }

        case 'agent_called':
        case 'agent_thinking': {
          if (agentId && newAgents[agentId]) {
            const role = newAgents[agentId].agent_role;
            const team = newAgents[agentId].team;
            const meetPos = getMeetingPosition(role) ?? newAgents[agentId].position;
            const nexusWP = getNexusWaypoint(team);

            // Step 1: stand up + walk toward NEXUS corridor
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'moving',
              pose: 'walking',
              position: nexusWP,
              current_task_id: (event.task_id as string | null) ?? newAgents[agentId].current_task_id,
            };

            // Step 2: after crossing the corridor, arrive at meeting seat
            const cId = agentId;
            const finalPos = meetPos;
            setTimeout(() => {
              set((s) => {
                if (!s.agents[cId]) return s;
                return {
                  agents: {
                    ...s.agents,
                    [cId]: { ...s.agents[cId], status: 'thinking', pose: 'standing', position: finalPos },
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
              // Walk back through the NEXUS corridor before sitting down
              const nexusWP = getNexusWaypoint(team);
              newAgents[agentId] = {
                ...newAgents[agentId],
                status: 'moving',
                pose: 'walking',
                position: nexusWP,
                current_task_id: null,
              };
              const cId = agentId;
              const finalPos = deskPos;
              setTimeout(() => {
                set((s) => {
                  if (!s.agents[cId]) return s;
                  return {
                    agents: {
                      ...s.agents,
                      [cId]: { ...s.agents[cId], status: 'idle', pose: 'seated', position: finalPos },
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
              };
            }
          }
          break;
        }

        case 'agent_status_changed':
        case 'agent_updated': {
          if (agentId && newAgents[agentId]) {
            const newStatus = event.status as Agent['status'];
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: newStatus || newAgents[agentId].status,
              current_task_id:
                (event.task_id as string | null) ?? newAgents[agentId].current_task_id,
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
            };
          }
          break;
        }

        case 'task_created': {
          if (taskId) {
            newTasks[taskId] = {
              ...newTasks[taskId],
              status: 'pending',
              request: String(event.request || event.description || newTasks[taskId].request),
            };
          }
          break;
        }

        case 'agent_assigned':
        case 'task_assigned': {
          if (taskId && newTasks[taskId]) {
            const payload = (event.payload as Record<string, unknown> | undefined) || {};
            newTasks[taskId] = {
              ...newTasks[taskId],
              status: 'assigned',
              request: String(payload.subtask_title || newTasks[taskId].request),
              assigned_agent_id: agentId || null,
            };
          }
          if (agentId && newAgents[agentId]) {
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'working',
              current_task_id: taskId ?? newAgents[agentId].current_task_id,
            };
          }
          break;
        }

        case 'task_started':
        case 'task_in_progress': {
          if (taskId && newTasks[taskId]) {
            const payload = (event.payload as Record<string, unknown> | undefined) || {};
            newTasks[taskId] = {
              ...newTasks[taskId],
              status: 'in_progress',
              request: String(
                payload.subtask_title ||
                payload.description ||
                newTasks[taskId].request
              ),
            };
          }
          if (agentId && newAgents[agentId]) {
            // Agent returns to desk to do the actual work
            const role = newAgents[agentId].agent_role;
            const team = newAgents[agentId].team;
            const deskPos = getDeskPosition(role) ?? newAgents[agentId].position;
            const inBoardroom = newAgents[agentId].position.y > 480;

            if (inBoardroom) {
              // Walk back from boardroom through NEXUS to desk
              const nexusWP = getNexusWaypoint(team);
              newAgents[agentId] = {
                ...newAgents[agentId],
                status: 'moving',
                pose: 'walking',
                position: nexusWP,
                current_task_id: taskId ?? newAgents[agentId].current_task_id,
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
              };
            }
          }
          break;
        }

        case 'task_completed': {
          const payload = (event.payload as Record<string, unknown> | undefined) || {};
          const isFinalTaskEvent =
            typeof payload.output_length === 'number' ||
            typeof payload.subtask_count === 'number';

          if (taskId && newTasks[taskId]) {
            newTasks[taskId] = {
              ...newTasks[taskId],
              status: isFinalTaskEvent ? 'completed' : 'in_progress',
            };
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
              completed_tasks: isFinalTaskEvent
                ? newAgents[agentId].completed_tasks + 1
                : newAgents[agentId].completed_tasks,
            };
          }
          break;
        }

        case 'task_failed': {
          if (taskId && newTasks[taskId]) {
            newTasks[taskId] = { ...newTasks[taskId], status: 'failed' };
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
            };
          }
          break;
        }

        default:
          break;
      }

      // Enqueue animation item with 500ms buffer timestamp
      if (agentId) {
        newQueue.push({
          event_type: eventType,
          agent_id: agentId,
          payload: event,
          timestamp: Date.now() + 500,
        });

        if (activityItem) {
          const current = newActivity[agentId] || [];
          newActivity[agentId] = [activityItem, ...current].slice(0, 12);
        }
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
    const now = Date.now();
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
          [agentId]: { ...agent, status: 'moving', position },
        },
      };
    });
  },

  wanderIdleAgents: () => {
    set((state) => {
      const updated: Record<string, Agent> = {};
      for (const [id, agent] of Object.entries(state.agents)) {
        // Only micro-fidget agents that are seated and idle at their desks
        if (agent.status !== 'idle' || agent.pose !== 'seated') continue;
        if (Math.random() > 0.25) continue; // 25% chance per tick — subtle
        const base = getDeskPosition(agent.agent_role) ?? agent.position;
        updated[id] = {
          ...agent,
          // Tiny ±4px range: keeps the agent alive-looking without jarring teleports
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
