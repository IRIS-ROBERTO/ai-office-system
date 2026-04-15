import type { Agent, Task, TaskBucket, TaskStatus } from '../../state/officeStore';
import { getTaskBucket } from '../../state/officeStore';

export function formatDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;

  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${rest.toString().padStart(2, '0')}s`;
  return `${rest}s`;
}

export function formatTimestamp(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

export function formatShortDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return '0s';
  return formatDuration(seconds);
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    idle: 'Idle',
    thinking: 'Thinking',
    working: 'Working',
    moving: 'Moving',
    queued: 'Queue',
    pending: 'Queue',
    assigned: 'Running',
    running: 'Running',
    in_progress: 'Running',
    validation: 'Validation',
    completed: 'Done',
    done: 'Done',
    failed: 'Failed',
    blocked: 'Blocked',
  };
  return map[status] ?? status;
}

export function zoneLabel(zone: string): string {
  const map: Record<string, string> = {
    'dev-zone': 'Dev Zone',
    'mind-zone': 'Mind Zone',
    'creative-lab': 'Creative Lab',
    boardroom: 'Boardroom',
    lounge: 'Lounge',
  };
  return map[zone] ?? zone;
}

export function taskBucketLabel(bucket: TaskBucket): string {
  const map: Record<TaskBucket, string> = {
    queue: 'Queue',
    running: 'Running',
    done: 'Done',
    failed: 'Failed',
    blocked: 'Blocked',
  };
  return map[bucket];
}

export function taskStatusTone(status: TaskStatus | string): string {
  const map: Record<string, string> = {
    queued: '#94a3b8',
    pending: '#94a3b8',
    assigned: '#818cf8',
    running: '#f59e0b',
    in_progress: '#f59e0b',
    validation: '#38bdf8',
    completed: '#22c55e',
    done: '#22c55e',
    failed: '#ef4444',
    blocked: '#f97316',
    idle: '#64748b',
    thinking: '#fbbf24',
    working: '#22c55e',
    moving: '#60a5fa',
  };
  return map[status] ?? '#94a3b8';
}

export function agentAccent(agent: Agent): string {
  if (agent.team === 'orchestrator') return '#fbbf24';
  if (agent.team === 'dev') return agent.color || '#60a5fa';
  return agent.color || '#c084fc';
}

export function bucketTask(task: Task): TaskBucket {
  return getTaskBucket(task.status);
}

export function compactTaskLabel(task: Task): string {
  const prefix = task.request.trim().slice(0, 54);
  return prefix.length < task.request.trim().length ? `${prefix}…` : prefix;
}
