import React, { useMemo } from 'react';
import type { Agent } from '../../state/officeStore';
import type { OfficeTask } from '../../types/operations';

interface ControlTowerProps {
  connected: boolean;
  agents: Agent[];
  tasks: OfficeTask[];
}

const panelStyle: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: '1.8fr 1.3fr 1fr',
  gap: 16,
  padding: 18,
  borderRadius: 24,
  border: '1px solid rgba(255,255,255,0.08)',
  background:
    'linear-gradient(180deg, rgba(9,12,20,0.94), rgba(6,8,14,0.92))',
  boxShadow: '0 24px 80px rgba(0,0,0,0.35)',
};

function badgeColor(state: string) {
  switch (state) {
    case 'healthy':
      return '#22c55e';
    case 'warning':
      return '#f59e0b';
    case 'breached':
      return '#ef4444';
    default:
      return '#94a3b8';
  }
}

export function ControlTower({ connected, agents, tasks }: ControlTowerProps) {
  const metrics = useMemo(() => {
    const queue = tasks.filter((task) => ['received', 'triage', 'planned'].includes(task.status)).length;
    const running = tasks.filter((task) => ['in_execution', 'in_testing', 'awaiting_approval'].includes(task.status)).length;
    const done = tasks.filter((task) => task.status === 'completed').length;
    const failed = tasks.filter((task) => ['changes_requested', 'failed'].includes(task.status)).length;
    const activeAlerts = tasks.filter((task) => task.slaState !== 'healthy' || task.bottlenecks.length > 0).length;
    const highestPriority = tasks.find((task) => task.status !== 'completed');

    return { queue, running, done, failed, activeAlerts, highestPriority };
  }, [tasks]);

  const crown = agents.find((agent) => agent.agent_role.includes('orchestrator'));
  const collaborating = agents.filter((agent) => agent.status === 'thinking' || agent.status === 'moving').length;

  return (
    <section style={panelStyle}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, letterSpacing: 2, textTransform: 'uppercase', color: '#fbbf24' }}>
              Control Tower
            </div>
            <h2 style={{ marginTop: 8, fontSize: 26, lineHeight: 1.1, color: '#f8fafc' }}>
              CROWN governa fila, squads e prioridade global.
            </h2>
          </div>
          <div style={{
            minWidth: 148,
            padding: 14,
            borderRadius: 18,
            background: 'radial-gradient(circle at top, rgba(251,191,36,0.18), rgba(251,191,36,0.04))',
            border: '1px solid rgba(251,191,36,0.3)',
          }}>
            <div style={{ fontSize: 10, letterSpacing: 1.5, textTransform: 'uppercase', color: '#fbbf24' }}>
              CROWN
            </div>
            <div style={{ marginTop: 6, fontSize: 18, fontWeight: 800, color: '#f8fafc' }}>
              {crown?.agent_name ?? 'Offline'}
            </div>
            <div style={{ marginTop: 4, fontSize: 12, color: connected ? '#22c55e' : '#ef4444' }}>
              {connected ? 'telemetria ativa' : 'telemetria offline'}
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12 }}>
          {[
            { label: 'Queue', value: metrics.queue, color: '#94a3b8' },
            { label: 'Running', value: metrics.running, color: '#38bdf8' },
            { label: 'Done', value: metrics.done, color: '#22c55e' },
            { label: 'Failed', value: metrics.failed, color: '#ef4444' },
          ].map((item) => (
            <div
              key={item.label}
              style={{
                padding: 14,
                borderRadius: 18,
                border: `1px solid ${item.color}33`,
                background: `${item.color}12`,
              }}
            >
              <div style={{ fontSize: 11, color: '#94a3b8', letterSpacing: 1.4, textTransform: 'uppercase' }}>
                {item.label}
              </div>
              <div style={{ marginTop: 8, fontSize: 28, fontWeight: 800, color: item.color }}>
                {item.value}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: 14 }}>
        <div style={{
          padding: 16,
          borderRadius: 20,
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.08)',
        }}>
          <div style={{ fontSize: 11, color: '#94a3b8', letterSpacing: 1.4, textTransform: 'uppercase' }}>
            Prioridade Global
          </div>
          {metrics.highestPriority ? (
            <>
              <div style={{ marginTop: 8, fontSize: 19, fontWeight: 700, color: '#f8fafc' }}>
                P{metrics.highestPriority.priority} · {metrics.highestPriority.title}
              </div>
              <div style={{ marginTop: 6, fontSize: 13, lineHeight: 1.6, color: '#cbd5e1' }}>
                {metrics.highestPriority.stageLabel} com {metrics.highestPriority.queueMinutes} min de espera.
              </div>
              <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <span style={chipStyle('#0ea5e9')}>{metrics.highestPriority.team.toUpperCase()}</span>
                <span style={chipStyle('#fbbf24')}>{metrics.highestPriority.currentAgentRole ?? 'sem dono atual'}</span>
                <span style={chipStyle(badgeColor(metrics.highestPriority.slaState))}>
                  SLA {metrics.highestPriority.slaState}
                </span>
              </div>
            </>
          ) : (
            <div style={{ marginTop: 10, color: '#94a3b8' }}>Nenhuma demanda aberta.</div>
          )}
        </div>

        <div style={{
          padding: 16,
          borderRadius: 20,
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.08)',
        }}>
          <div style={{ fontSize: 11, color: '#94a3b8', letterSpacing: 1.4, textTransform: 'uppercase' }}>
            Colaboração em tempo real
          </div>
          <div style={{ marginTop: 10, fontSize: 15, fontWeight: 700, color: '#f8fafc' }}>
            {collaborating} agentes em deslocamento, reunião ou raciocínio ativo
          </div>
          <div style={{ marginTop: 8, fontSize: 13, lineHeight: 1.6, color: '#cbd5e1' }}>
            O escritório agora mostra fluxo operacional: fila, squads temporários e gargalos críticos.
          </div>
        </div>
      </div>

      <div style={{
        padding: 16,
        borderRadius: 20,
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.08)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}>
        <div style={{ fontSize: 11, color: '#94a3b8', letterSpacing: 1.4, textTransform: 'uppercase' }}>
          Alertas críticos
        </div>
        <div style={{ fontSize: 30, fontWeight: 800, color: metrics.activeAlerts > 0 ? '#ef4444' : '#22c55e' }}>
          {metrics.activeAlerts}
        </div>
        <div style={{ fontSize: 13, lineHeight: 1.6, color: '#cbd5e1' }}>
          {metrics.activeAlerts > 0
            ? 'Há demandas em risco de SLA, sem teste, ou aguardando aprovação final.'
            : 'Sem alertas críticos no momento.'}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <span style={chipStyle(connected ? '#22c55e' : '#ef4444')}>{connected ? 'WS online' : 'WS offline'}</span>
          <span style={chipStyle('#8b5cf6')}>{agents.length} agentes</span>
          <span style={chipStyle('#fbbf24')}>{tasks.length} demandas</span>
        </div>
      </div>
    </section>
  );
}

function chipStyle(color: string): React.CSSProperties {
  return {
    padding: '6px 10px',
    borderRadius: 999,
    border: `1px solid ${color}44`,
    background: `${color}18`,
    color,
    fontSize: 11,
    letterSpacing: 0.6,
  };
}
