import type { Agent, Task } from '../../state/officeStore';
import { agentAccent, formatShortDuration, statusLabel, taskStatusTone } from './officeUtils';

interface AgentCardProps {
  agent: Agent;
  task: Task | null;
  selected?: boolean;
  now: number;
  onClick: (agentId: string) => void;
}

export function AgentCard({ agent, task, selected = false, now, onClick }: AgentCardProps) {
  const accent = agentAccent(agent);
  const taskLabel = task?.request || agent.task_summary || 'Monitoring queue and historical context';
  const etaSeconds = agent.task_eta_seconds ?? (task ? Math.max(45, Math.ceil((task.sla_seconds - task.wait_seconds) * 0.35)) : null);
  const deps = task?.dependencies ?? agent.task_dependencies ?? [];
  const stageIndex = task?.pipeline.findIndex((step) => step.status === 'active') ?? -1;
  const ageSeconds = task?.created_at ? Math.max(0, Math.floor((now - task.created_at) / 1000)) : 0;

  return (
    <button className={`agent-card ${selected ? 'agent-card--selected' : ''}`} onClick={() => onClick(agent.agent_id)}>
      <div className="agent-card__header">
        <div className="agent-avatar" style={{ background: `radial-gradient(circle at 30% 30%, ${accent}, rgba(255,255,255,0.08))` }} />
        <div className="agent-card__identity">
          <div className="agent-card__name">{agent.agent_name}</div>
          <div className="agent-card__role">{agent.agent_role}</div>
        </div>
        <span className="status-chip" style={{ color: taskStatusTone(agent.status), borderColor: `${taskStatusTone(agent.status)}55` }}>
          {statusLabel(agent.status)}
        </span>
      </div>

      <div className="agent-card__summary">{taskLabel}</div>

      <div className="agent-card__meta">
        <span>ETA {etaSeconds ? formatShortDuration(etaSeconds) : '—'}</span>
        <span>WAIT {task ? formatShortDuration(task.wait_seconds) : '—'}</span>
        <span>AGE {task ? formatShortDuration(ageSeconds) : '—'}</span>
      </div>

      <div className="agent-card__flow">
        {task?.pipeline.map((step, index) => (
          <div key={step.key} className={`flow-step flow-step--${step.status}`}>
            <span>{index + 1}</span>
            <small>{step.label}</small>
          </div>
        )) ?? (
          <div className="agent-card__idle-line">
            {agent.status === 'idle' ? 'Idle but auditing the backlog' : 'No task pipeline attached'}
          </div>
        )}
      </div>

      <div className="agent-card__footer">
        <div className="agent-tag" style={{ color: accent, borderColor: `${accent}44` }}>
          {agent.team.toUpperCase()}
        </div>
        <div className="agent-card__deps">
          {deps.length > 0 ? `Deps ${deps.slice(0, 2).join(', ')}` : 'No dependencies'}
        </div>
        <div className="agent-card__stage">
          {task ? `stage ${task.stage}${stageIndex >= 0 ? ` · step ${stageIndex + 1}/4` : ''}` : 'standby'}
        </div>
      </div>
    </button>
  );
}

export default AgentCard;
