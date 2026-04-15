import React from 'react';
import { getAgentProfile } from '../../data/agentProfiles';
import { useOfficeStore } from '../../state/officeStore';
import type { OfficeTask } from '../../types/operations';

interface AgentDetailsModalProps {
  agentId: string | null;
  tasks: OfficeTask[];
  onClose: () => void;
}

export function AgentDetailsModal({ agentId, tasks, onClose }: AgentDetailsModalProps) {
  const agent = useOfficeStore((state) => (agentId ? state.agents[agentId] : null));
  const activity = useOfficeStore((state) => (agentId ? state.agentActivity[agentId] ?? [] : []));

  if (!agent) return null;

  const profile = getAgentProfile(agent.agent_id, agent.agent_role);
  const currentTask = tasks.find((task) => task.taskId === agent.current_task_id) ?? null;
  const dependencies = currentTask?.involvedRoles.filter((role) => role !== agent.agent_role) ?? [];

  return (
    <div style={backdropStyle} onClick={onClose}>
      <div style={panelStyle} onClick={(event) => event.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'start', justifyContent: 'space-between', gap: 14 }}>
          <div style={{ display: 'flex', gap: 14 }}>
            <div style={{
              width: 56,
              height: 56,
              borderRadius: 16,
              background: `radial-gradient(circle at 30% 30%, ${agent.color}, rgba(15,23,42,0.3))`,
              boxShadow: `0 0 24px ${agent.color}55`,
            }} />
            <div>
              <div style={{ fontSize: 12, color: agent.color, letterSpacing: 1.4, textTransform: 'uppercase' }}>
                {agent.team}
              </div>
              <div style={{ marginTop: 6, fontSize: 24, fontWeight: 800, color: '#f8fafc' }}>
                {agent.agent_name}
              </div>
              <div style={{ marginTop: 4, fontSize: 13, color: '#cbd5e1' }}>{profile.title}</div>
            </div>
          </div>
          <button onClick={onClose} style={closeStyle}>×</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 16 }}>
          <div style={cardStyle}>
            <div style={titleStyle}>Estado atual</div>
            <div style={{ fontSize: 15, color: '#f8fafc', fontWeight: 700 }}>{agent.status}</div>
            <div style={{ marginTop: 10, fontSize: 13, lineHeight: 1.65, color: '#cbd5e1' }}>
              {profile.summary}
            </div>
            <div style={{ marginTop: 14, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {profile.strengths.slice(0, 4).map((item) => (
                <span key={item} style={pillStyle(agent.color)}>{item}</span>
              ))}
            </div>
          </div>

          <div style={cardStyle}>
            <div style={titleStyle}>Tarefa atual</div>
            {currentTask ? (
              <>
                <div style={{ fontSize: 15, fontWeight: 700, color: '#f8fafc' }}>{currentTask.title}</div>
                <div style={{ marginTop: 8, fontSize: 13, color: '#cbd5e1', lineHeight: 1.6 }}>
                  {currentTask.stageLabel} · prioridade {currentTask.priority}
                </div>
                <div style={{ marginTop: 10, fontSize: 12, color: '#94a3b8', lineHeight: 1.6 }}>
                  Dependências: {dependencies.length > 0 ? dependencies.join(', ') : 'sem dependências explícitas'}
                </div>
              </>
            ) : (
              <div style={{ color: '#94a3b8' }}>Sem tarefa vinculada no momento.</div>
            )}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={cardStyle}>
            <div style={titleStyle}>Histórico recente</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {activity.slice(0, 6).map((item) => (
                <div key={item.id} style={{
                  padding: '10px 12px',
                  borderRadius: 14,
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <div style={{ fontSize: 11, color: item.tone }}>{item.event_type}</div>
                  <div style={{ marginTop: 4, fontSize: 13, color: '#e2e8f0', lineHeight: 1.55 }}>
                    {item.message}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div style={cardStyle}>
            <div style={titleStyle}>Input / Output</div>
            <div style={{ fontSize: 13, color: '#cbd5e1', lineHeight: 1.65 }}>
              {currentTask
                ? currentTask.request.slice(0, 420)
                : 'Sem payload operacional para mostrar.'}
            </div>
            {currentTask?.lastExecutionMessage && (
              <div style={{
                marginTop: 12,
                padding: '10px 12px',
                borderRadius: 14,
                background: 'rgba(56,189,248,0.12)',
                border: '1px solid rgba(56,189,248,0.24)',
                color: '#bae6fd',
                fontSize: 13,
                lineHeight: 1.55,
              }}>
                {currentTask.lastExecutionMessage}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

const backdropStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  display: 'grid',
  placeItems: 'center',
  background: 'rgba(2,6,23,0.64)',
  backdropFilter: 'blur(10px)',
  zIndex: 90,
};

const panelStyle: React.CSSProperties = {
  width: 'min(920px, calc(100vw - 48px))',
  maxHeight: 'calc(100vh - 48px)',
  overflow: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: 16,
  padding: 20,
  borderRadius: 26,
  border: '1px solid rgba(255,255,255,0.1)',
  background: 'linear-gradient(180deg, rgba(10,13,22,0.98), rgba(6,8,14,0.96))',
  boxShadow: '0 32px 90px rgba(0,0,0,0.45)',
};

const closeStyle: React.CSSProperties = {
  width: 36,
  height: 36,
  borderRadius: 12,
  border: '1px solid rgba(255,255,255,0.1)',
  background: 'rgba(255,255,255,0.03)',
  color: '#94a3b8',
  fontSize: 22,
};

const cardStyle: React.CSSProperties = {
  padding: 16,
  borderRadius: 20,
  border: '1px solid rgba(255,255,255,0.08)',
  background: 'rgba(255,255,255,0.03)',
};

const titleStyle: React.CSSProperties = {
  marginBottom: 10,
  fontSize: 11,
  color: '#94a3b8',
  letterSpacing: 1.4,
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
