import React from 'react';
import type { Agent } from '../../state/officeStore';
import type { OfficeTask } from '../../types/operations';

interface LoungeProps {
  agents: Agent[];
  tasks: OfficeTask[];
}

export function Lounge({ agents, tasks }: LoungeProps) {
  const idleAgents = agents.filter((agent) => agent.status === 'idle');
  const latestTask = tasks[0];

  return (
    <section style={panelStyle}>
      <div style={titleStyle}>Lounge</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: '#f8fafc' }}>
        Idle inteligente com aprendizado contínuo
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.6, color: '#cbd5e1' }}>
        Agentes sem carga imediata ficam em observação, lendo histórico e preparando contexto para a próxima repriorização.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={cardStyle}>
          <div style={cardTitleStyle}>Agentes ociosos</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {idleAgents.map((agent) => (
              <span key={agent.agent_id} style={pillStyle(agent.color)}>
                {agent.agent_name}
              </span>
            ))}
          </div>
        </div>

        <div style={cardStyle}>
          <div style={cardTitleStyle}>Aprendizado atual</div>
          <div style={{ fontSize: 13, color: '#e2e8f0', lineHeight: 1.6 }}>
            {latestTask
              ? `Observando a demanda "${latestTask.title}" para reduzir tempo de triagem e preparar handoffs futuros.`
              : 'Sem backlog ativo. O lounge mantém histórico quente para o próximo ciclo.'}
          </div>
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
  color: '#22c55e',
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
