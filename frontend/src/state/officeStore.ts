import { create } from 'zustand';

export interface Agent {
  agent_id: string;
  agent_name: string;        // Codinome: ATLAS, PIXEL, FORGE, etc.
  agent_role: string;
  team: 'dev' | 'marketing';
  status: 'idle' | 'thinking' | 'working' | 'moving';
  current_task_id: string | null;
  position: { x: number; y: number };
  color: string;
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

interface OfficeStore {
  agents: Record<string, Agent>;
  tasks: Record<string, Task>;
  animationQueue: AnimationQueueItem[];
  connected: boolean;

  // Actions
  processEvent: (event: Record<string, unknown>) => void;
  setConnected: (v: boolean) => void;
  dequeueAnimation: () => AnimationQueueItem | undefined;
  getAgentsByTeam: (team: string) => Agent[];
}

// ── Agent identity registry — codinomes + cores por role ─────────────────────
// DEV  team: frios (azul, ciano, verde)
// MKT  team: quentes (roxo, rosa, âmbar)
// Cada agente tem cor única para identificação no canvas
export const AGENT_CODENAMES: Record<string, string> = {
  // Dev Team
  dev_planner_01:  'ATLAS',
  dev_frontend_01: 'PIXEL',
  dev_backend_01:  'FORGE',
  dev_qa_01:       'SHERLOCK',
  dev_security_01: 'AEGIS',
  dev_docs_01:     'LORE',
  // Marketing Team
  mkt_research_01: 'ORACLE',
  mkt_strategy_01: 'MAVEN',
  mkt_content_01:  'NOVA',
  mkt_seo_01:      'APEX',
  mkt_social_01:   'PULSE',
  mkt_analytics_01:'PRISM',
};

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
  index: number
): { x: number; y: number } {
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
  const uiTeam: 'dev' | 'marketing' = effectiveTeam === 'orchestrator' ? 'dev' : effectiveTeam;
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
      AGENT_CODENAMES[agentId] ||
      role.split(' ')[0].toUpperCase(),
    agent_role: role,
    team: uiTeam,
    status: 'idle',
    current_task_id: null,
    position:
      (event.position as { x: number; y: number } | undefined) ||
      getDefaultPosition(effectiveTeam, idx),
    color: getRoleColor(role),
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

export const useOfficeStore = create<OfficeStore>((set, get) => ({
  agents: {},
  tasks: {},
  animationQueue: [],
  connected: false,

  setConnected: (v) => set({ connected: v }),

  processEvent: (event) => {
    const eventType = String(event.event_type || '');

    set((state) => {
      const newAgents = { ...state.agents };
      const newTasks = { ...state.tasks };
      const newQueue = [...state.animationQueue];
      const agentId = ensureAgent(newAgents, event);
      const taskId = ensureTask(newTasks, event);

      switch (eventType) {
        case 'agent_registered':
        case 'agent_created': {
          break;
        }

        case 'agent_called':
        case 'agent_thinking': {
          if (agentId && newAgents[agentId]) {
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'thinking',
              current_task_id: (event.task_id as string | null) ?? newAgents[agentId].current_task_id,
            };
          }
          break;
        }

        case 'agent_idle': {
          if (agentId && newAgents[agentId]) {
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'idle',
              current_task_id: null,
            };
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
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'working',
              current_task_id: taskId ?? newAgents[agentId].current_task_id,
            };
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
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: isFinalTaskEvent ? 'idle' : newAgents[agentId].status,
              current_task_id: isFinalTaskEvent ? null : newAgents[agentId].current_task_id,
            };
          }
          break;
        }

        case 'task_failed': {
          if (taskId && newTasks[taskId]) {
            newTasks[taskId] = { ...newTasks[taskId], status: 'failed' };
          }
          if (agentId && newAgents[agentId]) {
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'idle',
              current_task_id: null,
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
      }

      return { agents: newAgents, tasks: newTasks, animationQueue: newQueue };
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
}));
