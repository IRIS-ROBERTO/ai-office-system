import type { Agent, Task } from '../../state/officeStore';
import { compactTaskLabel, formatShortDuration, taskBucketLabel, taskStatusTone } from './officeUtils';

interface TaskNodeProps {
  task: Task;
  agents: Record<string, Agent>;
  selected?: boolean;
  now: number;
  onClick: (taskId: string) => void;
}

export function TaskNode({ task, agents, selected = false, now, onClick }: TaskNodeProps) {
  const assignees = task.assigned_agent_ids
    .map((agentId) => agents[agentId]?.agent_name || agentId.slice(0, 6))
    .filter(Boolean);
  const waitSeconds = Math.max(0, Math.floor((now - task.created_at) / 1000));
  const progress = Math.min(100, Math.max(task.progress, task.status === 'completed' || task.status === 'done' ? 100 : task.status === 'failed' ? 60 : task.progress));

  return (
    <button className={`task-node ${selected ? 'task-node--selected' : ''}`} onClick={() => onClick(task.task_id)}>
      <div className="task-node__top">
        <div>
          <div className="eyebrow">Task {task.task_id.slice(0, 8)}</div>
          <h3 className="task-node__title">{compactTaskLabel(task)}</h3>
        </div>
        <div className="task-node__stack">
          <span className="priority-pill">P{task.priority}</span>
          <span className="status-chip" style={{ color: taskStatusTone(task.status), borderColor: `${taskStatusTone(task.status)}55` }}>
            {taskBucketLabel(task.status === 'failed' ? 'failed' : task.status === 'blocked' ? 'blocked' : task.status === 'completed' || task.status === 'done' ? 'done' : task.status === 'running' || task.status === 'in_progress' || task.status === 'assigned' ? 'running' : 'queue')}
          </span>
        </div>
      </div>

      <div className="task-node__body">
        <div className="task-node__request">{task.request}</div>
        <div className="task-node__stats">
          <span>WAIT {formatShortDuration(waitSeconds)}</span>
          <span>SLA {formatShortDuration(task.sla_seconds)}</span>
          <span>{assignees.length > 0 ? assignees.join(' · ') : 'No agent yet'}</span>
        </div>

        <div className="task-node__progress">
          <div className="task-node__progress-bar" style={{ width: `${progress}%`, background: taskStatusTone(task.status) }} />
        </div>

        <div className="task-node__pipeline">
          {task.pipeline.map((step) => (
            <div key={step.key} className={`pipeline-step pipeline-step--${step.status}`}>
              <span>{step.label}</span>
              <small>{step.agent_id ? (agents[step.agent_id]?.agent_name || step.agent_id.slice(0, 6)) : 'Unassigned'}</small>
            </div>
          ))}
        </div>
      </div>
    </button>
  );
}

export default TaskNode;
