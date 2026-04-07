import { create } from 'zustand';

export interface Agent {
  agent_id: string;
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

// Role color mapping
const ROLE_COLORS: Record<string, string> = {
  // Dev team
  planner: '#3b82f6',       // blue
  backend: '#ef4444',        // red
  frontend: '#22c55e',       // green
  research: '#10b981',       // emerald green
  devops: '#f59e0b',         // amber
  qa: '#a855f7',             // purple
  architect: '#06b6d4',      // cyan
  // Marketing team
  strategy: '#6366f1',       // indigo
  copywriter: '#ec4899',     // pink
  designer: '#f97316',       // orange
  analyst: '#14b8a6',        // teal
  social: '#8b5cf6',         // violet
  seo: '#84cc16',            // lime
  // Orchestrators
  orchestrator: '#fbbf24',   // yellow
  manager: '#fbbf24',
};

// Default positions for agents in their respective team zones
const DEV_ZONE = { xMin: 30, xMax: 550, yMin: 80, yMax: 620 };
const MARKETING_ZONE = { xMin: 730, xMax: 1250, yMin: 80, yMax: 620 };
const ORCHESTRATOR_ZONE = { x: 640, yMin: 100, yMax: 620 };

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

export const useOfficeStore = create<OfficeStore>((set, get) => ({
  agents: {},
  tasks: {},
  animationQueue: [],
  connected: false,

  setConnected: (v) => set({ connected: v }),

  processEvent: (event) => {
    const eventType = event.event_type as string;
    const agentId = (event.agent_id || event.id) as string | undefined;

    set((state) => {
      const newAgents = { ...state.agents };
      const newTasks = { ...state.tasks };
      const newQueue = [...state.animationQueue];

      switch (eventType) {
        case 'agent_registered':
        case 'agent_created': {
          const role = (event.agent_role || event.role || 'worker') as string;
          const team = (event.team || 'dev') as 'dev' | 'marketing';
          const lowerRole = role.toLowerCase();
          const effectiveTeam: 'dev' | 'marketing' | 'orchestrator' =
            lowerRole.includes('orchestrator') || lowerRole.includes('manager')
              ? 'orchestrator'
              : team;

          const idx = agentIndexByTeam[effectiveTeam] ?? 0;
          agentIndexByTeam[effectiveTeam] = idx + 1;

          newAgents[agentId!] = {
            agent_id: agentId!,
            agent_role: role,
            team: effectiveTeam === 'orchestrator' ? 'dev' : effectiveTeam,
            status: 'idle',
            current_task_id: null,
            position: (event.position as { x: number; y: number }) ||
              getDefaultPosition(effectiveTeam, idx),
            color: getRoleColor(role),
          };
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
          const taskId = event.task_id as string;
          newTasks[taskId] = {
            task_id: taskId,
            team: (event.team || 'dev') as string,
            status: 'pending',
            request: (event.request || event.description || '') as string,
            assigned_agent_id: null,
          };
          break;
        }

        case 'task_assigned': {
          const taskId = event.task_id as string;
          if (newTasks[taskId]) {
            newTasks[taskId] = {
              ...newTasks[taskId],
              status: 'assigned',
              assigned_agent_id: agentId || null,
            };
          }
          if (agentId && newAgents[agentId]) {
            newAgents[agentId] = {
              ...newAgents[agentId],
              status: 'working',
              current_task_id: taskId,
            };
          }
          break;
        }

        case 'task_started': {
          const taskId = event.task_id as string;
          if (newTasks[taskId]) {
            newTasks[taskId] = { ...newTasks[taskId], status: 'in_progress' };
          }
          if (agentId && newAgents[agentId]) {
            newAgents[agentId] = { ...newAgents[agentId], status: 'working' };
          }
          break;
        }

        case 'agent_thinking': {
          if (agentId && newAgents[agentId]) {
            newAgents[agentId] = { ...newAgents[agentId], status: 'thinking' };
          }
          break;
        }

        case 'task_completed': {
          const taskId = event.task_id as string;
          if (newTasks[taskId]) {
            newTasks[taskId] = { ...newTasks[taskId], status: 'completed' };
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

        case 'task_failed': {
          const taskId = event.task_id as string;
          if (newTasks[taskId]) {
            newTasks[taskId] = { ...newTasks[taskId], status: 'failed' };
          }
          if (agentId && newAgents[agentId]) {
            newAgents[agentId] = { ...newAgents[agentId], status: 'idle' };
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
