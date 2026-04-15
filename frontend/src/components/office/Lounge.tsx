import type { Agent } from '../../state/officeStore';
import { agentAccent, statusLabel } from './officeUtils';

interface LoungeProps {
  agents: Agent[];
  now: number;
}

export function Lounge({ agents, now }: LoungeProps) {
  return (
    <section className="lounge panel-surface">
      <div className="lounge__header">
        <div>
          <div className="eyebrow">Lounge</div>
          <h3 className="shell-subtitle">Idle intelligence</h3>
        </div>
        <span className="subtle-chip">{agents.length} agents</span>
      </div>

      <div className="lounge__body">
        {agents.length === 0 ? (
          <div className="lounge__empty">No idle agents right now. The floor is fully engaged.</div>
        ) : (
          agents.map((agent) => (
            <div key={agent.agent_id} className="lounge-card">
              <div className="lounge-card__dot" style={{ background: agentAccent(agent) }} />
              <div className="lounge-card__content">
                <strong>{agent.agent_name}</strong>
                <span>{statusLabel(agent.status)}</span>
                <small>{agent.task_summary || 'Reviewing history and learning from the queue'}</small>
              </div>
              <div className="lounge-card__time">
                {new Date(now).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', hour12: false })}
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

export default Lounge;
