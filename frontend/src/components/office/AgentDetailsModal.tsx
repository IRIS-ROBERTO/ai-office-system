import type { MouseEvent } from 'react';
import { getAgentProfile } from '../../data/agentProfiles';
import type { Agent, AgentActivityItem, Task } from '../../state/officeStore';
import { PipelineFlow } from './PipelineFlow';
import { formatTimestamp, statusLabel, taskStatusTone } from './officeUtils';

interface AgentDetailsModalProps {
  agent: Agent;
  task: Task | null;
  activity: AgentActivityItem[];
  agents: Record<string, Agent>;
  onClose: () => void;
}

export function AgentDetailsModal({ agent, task, activity, agents, onClose }: AgentDetailsModalProps) {
  const profile = getAgentProfile(agent.agent_id, agent.agent_role);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="agent-modal panel-surface" onClick={(event: MouseEvent<HTMLDivElement>) => event.stopPropagation()}>
        <div className="agent-modal__header">
          <div>
            <div className="eyebrow">Agent details</div>
            <h3 className="shell-subtitle">{profile.codename}</h3>
          </div>
          <button className="subtle-chip subtle-chip--clickable" onClick={onClose}>Close</button>
        </div>

        <div className="agent-modal__identity">
          <div className="agent-avatar agent-avatar--large" style={{ background: `radial-gradient(circle at 30% 30%, ${agent.color}, rgba(255,255,255,0.12))` }} />
          <div>
            <strong>{profile.title}</strong>
            <p>{profile.summary}</p>
            <span>{agent.team.toUpperCase()} · {agent.agent_role}</span>
          </div>
        </div>

        <div className="agent-modal__metrics">
          <div>
            <span>Status</span>
            <strong style={{ color: taskStatusTone(agent.status) }}>{statusLabel(agent.status)}</strong>
          </div>
          <div>
            <span>Completed</span>
            <strong>{agent.completed_tasks}</strong>
          </div>
          <div>
            <span>Errors</span>
            <strong>{agent.error_count}</strong>
          </div>
          <div>
            <span>Current task</span>
            <strong>{task ? task.task_id.slice(0, 10) : 'None'}</strong>
          </div>
        </div>

        <div className="agent-modal__section">
          <div className="eyebrow">Live context</div>
          <p>{agent.task_summary || profile.mission}</p>
          <small>{agent.task_note || profile.signature}</small>
        </div>

        <PipelineFlow task={task} agents={agents} />

        <div className="agent-modal__section">
          <div className="eyebrow">Recent signals</div>
          <div className="agent-modal__log">
            {activity.length === 0 ? (
              <div className="agent-modal__empty">No activity recorded yet.</div>
            ) : (
              activity.slice(0, 6).map((item) => (
                <div key={item.id} className="agent-modal__log-item">
                  <span style={{ color: item.tone }}>●</span>
                  <div>
                    <strong>{item.message}</strong>
                    <small>{formatTimestamp(item.timestamp)}{item.task_id ? ` · ${item.task_id.slice(0, 8)}` : ''}</small>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default AgentDetailsModal;
