import type { Agent, Task } from '../../state/officeStore';
import { taskStatusTone } from './officeUtils';

interface PipelineFlowProps {
  task: Task | null;
  agents: Record<string, Agent>;
}

export function PipelineFlow({ task, agents }: PipelineFlowProps) {
  if (!task) {
    return (
      <div className="pipeline-flow panel-surface">
        <div className="eyebrow">Pipeline Flow</div>
        <div className="pipeline-flow__empty">Selecione uma tarefa para abrir o fluxo completo.</div>
      </div>
    );
  }

  const assigned = task.assigned_agent_ids
    .map((agentId) => agents[agentId]?.agent_name || agentId.slice(0, 8))
    .join(' → ');

  return (
    <div className="pipeline-flow panel-surface">
      <div className="pipeline-flow__header">
        <div>
          <div className="eyebrow">Pipeline Flow</div>
          <h3 className="shell-subtitle">{task.request}</h3>
        </div>
        <span className="priority-pill" style={{ borderColor: `${taskStatusTone(task.status)}44`, color: taskStatusTone(task.status) }}>
          {task.status}
        </span>
      </div>

      <div className="pipeline-flow__track">
        {task.pipeline.map((step, index) => (
          <div key={step.key} className={`pipeline-flow__step pipeline-flow__step--${step.status}`}>
            <span>{index + 1}</span>
            <strong>{step.label}</strong>
            <small>{step.agent_id ? (agents[step.agent_id]?.agent_name || step.agent_id.slice(0, 8)) : '—'}</small>
          </div>
        ))}
        <div className="pipeline-flow__rail" />
      </div>

      <div className="pipeline-flow__notes">
        <div>
          <span>Input</span>
          <p>{task.input || task.request}</p>
        </div>
        <div>
          <span>Validation</span>
          <p>{task.validation || 'Quality gate pending'}</p>
        </div>
        <div>
          <span>Output</span>
          <p>{task.output || 'Awaiting delivery'}</p>
        </div>
      </div>

      <div className="pipeline-flow__agents">
        <span className="tower-line__label">Agents involved</span>
        <strong>{assigned || 'No agents assigned yet'}</strong>
      </div>
    </div>
  );
}

export default PipelineFlow;
