import React from 'react';
import type { Agent } from '../../state/officeStore';
import type { ExecutionLogItem, OfficeTask } from '../../types/operations';

interface PipelineFlowProps {
  task: OfficeTask | null;
  agents: Agent[];
  logs: ExecutionLogItem[];
  loading: boolean;
}

function stateColor(state: string) {
  switch (state) {
    case 'completed':
      return '#22c55e';
    case 'active':
      return '#38bdf8';
    case 'failed':
      return '#ef4444';
    default:
      return '#64748b';
  }
}

export function PipelineFlow({ task, agents, logs, loading }: PipelineFlowProps) {
  if (!task) {
    return (
      <section style={emptyStyle}>
        Selecione uma tarefa para abrir pipeline, agentes envolvidos e gargalos.
      </section>
    );
  }

  const involvedAgents = agents.filter((agent) =>
    task.involvedRoles.some((role) => agent.agent_role.includes(role)),
  );
  const recentLogs = logs.slice(-6).reverse();

  return (
    <section style={panelStyle}>
      <div style={{ display: 'flex', alignItems: 'start', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{ fontSize: 11, color: '#38bdf8', letterSpacing: 1.4, textTransform: 'uppercase' }}>
            Pipeline Flow
          </div>
          <h3 style={{ marginTop: 6, fontSize: 24, color: '#f8fafc', lineHeight: 1.15 }}>
            {task.title}
          </h3>
          <div style={{ marginTop: 6, fontSize: 13, color: '#94a3b8', lineHeight: 1.6 }}>
            {task.stageLabel} · {task.currentAgentRole ?? 'orchestrator'} · {task.executionLogSize} eventos rastreados
          </div>
        </div>
        <div style={{
          padding: '8px 10px',
          borderRadius: 999,
          border: '1px solid rgba(251,191,36,0.3)',
          background: 'rgba(251,191,36,0.08)',
          color: '#fbbf24',
          fontSize: 11,
          letterSpacing: 1,
          textTransform: 'uppercase',
        }}>
          {task.status}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12 }}>
        {task.stages.map((stage, index) => (
          <div key={stage.id} style={{
            position: 'relative',
            padding: 14,
            borderRadius: 18,
            border: `1px solid ${stateColor(stage.state)}33`,
            background: `${stateColor(stage.state)}10`,
          }}>
            {index < task.stages.length - 1 && (
              <div style={{
                position: 'absolute',
                top: '50%',
                right: -14,
                width: 28,
                height: 2,
                background: stateColor(stage.state),
                opacity: 0.4,
              }} />
            )}
            <div style={{ fontSize: 10, color: '#94a3b8', letterSpacing: 1.3, textTransform: 'uppercase' }}>
              {stage.label}
            </div>
            <div style={{ marginTop: 8, fontSize: 14, fontWeight: 700, color: '#f8fafc' }}>
              {stage.owner}
            </div>
            <div style={{ marginTop: 6, fontSize: 12, lineHeight: 1.55, color: '#cbd5e1' }}>
              {stage.detail}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 14 }}>
        <div style={subPanelStyle}>
          <div style={subTitleStyle}>Agentes envolvidos</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {involvedAgents.map((agent) => (
              <div key={agent.agent_id} style={{
                padding: '10px 12px',
                borderRadius: 16,
                background: `${agent.color}18`,
                border: `1px solid ${agent.color}44`,
              }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#f8fafc' }}>{agent.agent_name}</div>
                <div style={{ marginTop: 4, fontSize: 11, color: agent.color }}>
                  {agent.agent_role} · {agent.status}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={subPanelStyle}>
          <div style={subTitleStyle}>Gargalos</div>
          {task.bottlenecks.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {task.bottlenecks.map((item) => (
                <div key={item} style={{
                  padding: '10px 12px',
                  borderRadius: 14,
                  border: '1px solid rgba(239,68,68,0.24)',
                  background: 'rgba(239,68,68,0.12)',
                  color: '#fecaca',
                  fontSize: 13,
                  lineHeight: 1.55,
                }}>
                  {item}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: '#cbd5e1', lineHeight: 1.6 }}>
              Nenhum gargalo explícito. O fluxo atual está sob controle operacional.
            </div>
          )}
        </div>
      </div>

      <div style={subPanelStyle}>
        <div style={subTitleStyle}>Execution log</div>
        {loading ? (
          <div style={{ color: '#94a3b8' }}>Carregando logs da tarefa…</div>
        ) : recentLogs.length > 0 ? (
          <div style={{ display: 'grid', gap: 8 }}>
            {recentLogs.map((item) => (
              <div key={`${item.timestamp}-${item.stage}`} style={{
                display: 'grid',
                gridTemplateColumns: '140px 1fr',
                gap: 10,
                padding: '10px 12px',
                borderRadius: 14,
                border: '1px solid rgba(255,255,255,0.06)',
                background: 'rgba(255,255,255,0.03)',
              }}>
                <div style={{ fontSize: 11, color: '#38bdf8', fontFamily: 'JetBrains Mono, monospace' }}>
                  {item.stage}
                </div>
                <div style={{ fontSize: 13, color: '#e2e8f0', lineHeight: 1.6 }}>
                  {item.message}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: '#94a3b8' }}>Nenhum log detalhado disponível para esta seleção.</div>
        )}
      </div>
    </section>
  );
}

const panelStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 16,
  padding: 18,
  borderRadius: 24,
  border: '1px solid rgba(255,255,255,0.08)',
  background: 'linear-gradient(180deg, rgba(9,12,20,0.94), rgba(6,8,14,0.92))',
};

const emptyStyle: React.CSSProperties = {
  ...panelStyle,
  alignItems: 'center',
  justifyContent: 'center',
  color: '#94a3b8',
  minHeight: 220,
};

const subPanelStyle: React.CSSProperties = {
  padding: 14,
  borderRadius: 18,
  border: '1px solid rgba(255,255,255,0.08)',
  background: 'rgba(255,255,255,0.03)',
};

const subTitleStyle: React.CSSProperties = {
  marginBottom: 10,
  fontSize: 11,
  color: '#94a3b8',
  letterSpacing: 1.4,
  textTransform: 'uppercase',
};
