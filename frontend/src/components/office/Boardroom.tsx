import type { Agent, Task } from '../../state/officeStore';
import { agentAccent, statusLabel } from './officeUtils';

interface BoardroomProps {
  agents: Agent[];
  selectedTask: Task | null;
  onAgentClick: (agentId: string) => void;
}

export function Boardroom({ agents, selectedTask, onAgentClick }: BoardroomProps) {
  const meetingAgents = agents.filter((agent) => agent.status !== 'idle');

  return (
    <section className="boardroom panel-surface">
      <div className="boardroom__header">
        <div>
          <div className="eyebrow">Boardroom</div>
          <h3 className="shell-subtitle">Collaboration ring</h3>
        </div>
        <span className="subtle-chip">{meetingAgents.length} in motion</span>
      </div>

      <div className="boardroom__table">
        <div className="boardroom__halo" />
        <div className="boardroom__center">
          <div className="boardroom__center-label">CROWN</div>
          <strong>{selectedTask ? selectedTask.request : 'Standing by for the next approval'}</strong>
        </div>
        {meetingAgents.slice(0, 8).map((agent, index) => (
          <button
            key={agent.agent_id}
            className="boardroom-seat"
            style={{
              transform: `rotate(${index * 45}deg) translateY(-162px) rotate(${-index * 45}deg)`,
              borderColor: `${agentAccent(agent)}55`,
            }}
            onClick={() => onAgentClick(agent.agent_id)}
          >
            <span className="boardroom-seat__dot" style={{ background: agentAccent(agent) }} />
            <strong>{agent.agent_name}</strong>
            <small>{statusLabel(agent.status)}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

export default Boardroom;
