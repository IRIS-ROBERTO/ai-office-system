import type { Agent, Task } from '../../state/officeStore';
import { bucketTask, formatDuration, formatShortDuration, statusLabel, taskStatusTone } from './officeUtils';
import { PipelineFlow } from './PipelineFlow';

interface TaskInspectorProps {
  task: Task | null;
  agents: Record<string, Agent>;
  now: number;
  onTaskSelect?: (taskId: string) => void;
}

export function TaskInspector({ task, agents, now, onTaskSelect }: TaskInspectorProps) {
  const orderedTasks = Object.values(agents).length;

  if (!task) {
    return (
      <section className="task-inspector panel-surface">
        <div className="eyebrow">Task Inspector</div>
        <div className="task-inspector__empty">
          Select a task to inspect the full pipeline, assignees, wait time and SLA pressure.
        </div>
        <div className="task-inspector__hint">Active agents in the office: {orderedTasks}</div>
      </section>
    );
  }

  const bucket = bucketTask(task);
  const waitSeconds = Math.max(0, Math.floor((now - task.created_at) / 1000));
  const deps = task.dependencies.length > 0 ? task.dependencies.join(' · ') : 'No dependencies recorded';
  const blockers = task.blockers.length > 0 ? task.blockers.join(' · ') : 'No blockers';
  const assignees = task.assigned_agent_ids
    .map((agentId) => agents[agentId]?.agent_name || agentId.slice(0, 8))
    .join(' · ');

  return (
    <section className="task-inspector panel-surface">
      <div className="task-inspector__header">
        <div>
          <div className="eyebrow">Task Inspector</div>
          <h3 className="shell-subtitle">{task.request}</h3>
        </div>
        <button className="subtle-chip subtle-chip--clickable" onClick={() => onTaskSelect?.(task.task_id)}>
          Focus
        </button>
      </div>

      <div className="task-inspector__meta">
        <span className="priority-pill">P{task.priority}</span>
        <span className="status-chip" style={{ color: taskStatusTone(task.status), borderColor: `${taskStatusTone(task.status)}55` }}>
          {statusLabel(task.status)}
        </span>
        <span className="subtle-chip">{bucket.toUpperCase()}</span>
      </div>

      <div className="task-inspector__stats">
        <div>
          <span>Wait</span>
          <strong>{formatDuration(waitSeconds)}</strong>
        </div>
        <div>
          <span>SLA</span>
          <strong>{formatShortDuration(task.sla_seconds)}</strong>
        </div>
        <div>
          <span>Progress</span>
          <strong>{task.progress}%</strong>
        </div>
      </div>

      <div className="task-inspector__note">
        <span>Input</span>
        <p>{task.input || task.request}</p>
      </div>

      <div className="task-inspector__note">
        <span>Dependencies</span>
        <p>{deps}</p>
      </div>

      <div className="task-inspector__note">
        <span>Blockers</span>
        <p>{blockers}</p>
      </div>

      <PipelineFlow task={task} agents={agents} />

      <div className="task-inspector__note">
        <span>Agents involved</span>
        <p>{assignees || 'None yet'}</p>
      </div>
    </section>
  );
}

export default TaskInspector;
