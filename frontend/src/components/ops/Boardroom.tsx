import React from 'react';
import type { Agent } from '../../state/officeStore';
import type { OfficeTask } from '../../types/operations';

interface BoardroomProps {
  agents: Agent[];
  tasks: OfficeTask[];
}

export function Boardroom({ agents, tasks }: BoardroomProps) {
  const collaborationAgents = agents.filter((agent) => agent.status === 'thinking' || agent.status === 'moving');
  const liveTasks = tasks.filter((task) => ['in_execution', 'in_testing', 'awaiting_approval'].includes(task.status));

  return (
    <section style={panelStyle}>
      <div style={titleStyle}>Boardroom</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: '#f8fafc' }}>
        Reuniões automáticas e squads temporários
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.6, color: '#cbd5e1' }}>
        O boardroom só recebe agentes quando existe motivo operacional: alinhamento, decisão, handoff ou aprovação.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={cardStyle}>
          <div style={cardTitleStyle}>Agentes em reunião</div>
          {collaborationAgents.length > 0 ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {collaborationAgents.map((agent) => (
                <span key={agent.agent_id} style={pillStyle(agent.color)}>
                  {agent.agent_name} · {agent.status}
                </span>
              ))}
            </div>
          ) : (
            <div style={{ color: '#94a3b8' }}>Nenhum agente em colaboração ativa agora.</div>
          )}
        </div>

        <div style={cardStyle}>
          <div style={cardTitleStyle}>Squads ativos</div>
          {liveTasks.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {liveTasks.map((task) => (
                <div key={task.requestId} style={{
                  padding: '10px 12px',
                  borderRadius: 14,
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>{task.title}</div>
                  <div style={{ marginTop: 4, fontSize: 12, color: '#cbd5e1' }}>
                    {task.involvedRoles.slice(0, 4).join(' → ')}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: '#94a3b8' }}>Nenhum squad temporário em formação.</div>
          )}
        </div>
      </div>
    </section>
  );
}

const panelStyle: React.CSSProperties = {
  padding: 18,
  borderRadius: 24,
  border: '1px solid rgba(255,255,255,0.08)',
  background: 'linear-gradient(180deg, rgba(9,12,20,0.94), rgba(6,8,14,0.92))',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
};

const titleStyle: React.CSSProperties = {
  fontSize: 11,
  color: '#fbbf24',
  letterSpacing: 1.5,
  textTransform: 'uppercase',
};

const cardStyle: React.CSSProperties = {
  padding: 14,
  borderRadius: 18,
  border: '1px solid rgba(255,255,255,0.08)',
  background: 'rgba(255,255,255,0.03)',
};

const cardTitleStyle: React.CSSProperties = {
  marginBottom: 10,
  fontSize: 11,
  color: '#94a3b8',
  letterSpacing: 1.3,
  textTransform: 'uppercase',
};

function pillStyle(color: string): React.CSSProperties {
  return {
    padding: '6px 10px',
    borderRadius: 999,
    border: `1px solid ${color}44`,
    background: `${color}18`,
    color,
    fontSize: 11,
  };
}
