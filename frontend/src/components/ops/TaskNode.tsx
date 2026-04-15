import React from 'react';
import type { OfficeTask } from '../../types/operations';
import { formatDateLabel, formatMinutes } from '../../utils/operations';

interface TaskNodeProps {
  task: OfficeTask;
  selected: boolean;
  onClick: (taskId: string) => void;
}

function priorityColor(priority: number) {
  if (priority >= 4) return '#ef4444';
  if (priority === 3) return '#f97316';
  if (priority === 2) return '#38bdf8';
  return '#94a3b8';
}

function statusColor(status: string) {
  switch (status) {
    case 'completed':
      return '#22c55e';
    case 'changes_requested':
    case 'failed':
      return '#ef4444';
    case 'awaiting_approval':
      return '#fbbf24';
    case 'in_testing':
      return '#8b5cf6';
    default:
      return '#38bdf8';
  }
}

export function TaskNode({ task, selected, onClick }: TaskNodeProps) {
  return (
    <button
      onClick={() => onClick(task.requestId)}
      style={{
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        textAlign: 'left',
        padding: 14,
        borderRadius: 18,
        border: `1px solid ${selected ? '#fbbf24' : 'rgba(255,255,255,0.08)'}`,
        background: selected ? 'rgba(251,191,36,0.12)' : 'rgba(255,255,255,0.03)',
        boxShadow: selected ? '0 18px 40px rgba(251,191,36,0.12)' : 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'start', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{ fontSize: 10, color: '#94a3b8', letterSpacing: 1.4, textTransform: 'uppercase' }}>
            {task.team.toUpperCase()} · {task.stageLabel}
          </div>
          <div style={{ marginTop: 6, fontSize: 16, fontWeight: 700, color: '#f8fafc', lineHeight: 1.25 }}>
            {task.title}
          </div>
        </div>
        <span style={{
          padding: '4px 8px',
          borderRadius: 999,
          background: `${priorityColor(task.priority)}18`,
          border: `1px solid ${priorityColor(task.priority)}44`,
          color: priorityColor(task.priority),
          fontSize: 11,
          fontWeight: 700,
        }}>
          P{task.priority}
        </span>
      </div>

      <div style={{ fontSize: 13, lineHeight: 1.55, color: '#cbd5e1' }}>
        {task.request.slice(0, 160)}{task.request.length > 160 ? '…' : ''}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
        <Metric label="Fila" value={formatMinutes(task.queueMinutes)} />
        <Metric label="SLA" value={task.slaState} color={task.slaState === 'breached' ? '#ef4444' : task.slaState === 'warning' ? '#f59e0b' : '#22c55e'} />
        <Metric label="Agente" value={task.currentAgentRole ?? 'CROWN'} color="#fbbf24" />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <span style={badgeStyle(statusColor(task.status))}>{task.status}</span>
          <span style={badgeStyle('#8b5cf6')}>{task.executionLogSize} logs</span>
        </div>
        <div style={{ fontSize: 11, color: '#94a3b8' }}>
          {formatDateLabel(task.desiredDueDate)}
        </div>
      </div>
    </button>
  );
}

function Metric({ label, value, color = '#f8fafc' }: { label: string; value: string; color?: string }) {
  return (
    <div style={{
      padding: 10,
      borderRadius: 14,
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)',
    }}>
      <div style={{ fontSize: 10, color: '#64748b', letterSpacing: 1.1, textTransform: 'uppercase' }}>
        {label}
      </div>
      <div style={{ marginTop: 6, fontSize: 13, fontWeight: 700, color }}>
        {value}
      </div>
    </div>
  );
}

function badgeStyle(color: string): React.CSSProperties {
  return {
    padding: '5px 8px',
    borderRadius: 999,
    border: `1px solid ${color}44`,
    background: `${color}18`,
    color,
    fontSize: 10,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  };
}
