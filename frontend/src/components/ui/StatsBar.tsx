import React from 'react';
import { useOfficeStore } from '../../state/officeStore';

export const StatsBar: React.FC = () => {
  const agents = useOfficeStore((s) => s.agents);
  const tasks = useOfficeStore((s) => s.tasks);

  const agentList = Object.values(agents);
  const taskList = Object.values(tasks);

  const working = agentList.filter((a) => a.status === 'working').length;
  const thinking = agentList.filter((a) => a.status === 'thinking').length;
  const idle = agentList.filter((a) => a.status === 'idle').length;

  const pending = taskList.filter((t) => t.status === 'pending').length;
  const inProgress = taskList.filter((t) => t.status === 'in_progress').length;
  const completed = taskList.filter((t) => t.status === 'completed').length;

  return (
    <div style={styles.bar}>
      <StatItem label="Agents" value={agentList.length} color="#94a3b8" />
      <Divider />
      <StatItem label="Working" value={working} color="#22c55e" />
      <StatItem label="Thinking" value={thinking} color="#a855f7" />
      <StatItem label="Idle" value={idle} color="#64748b" />
      <Divider />
      <StatItem label="Tasks" value={taskList.length} color="#94a3b8" />
      <StatItem label="In Progress" value={inProgress} color="#f59e0b" />
      <StatItem label="Done" value={completed} color="#22c55e" />
      <StatItem label="Pending" value={pending} color="#6b7280" />
    </div>
  );
};

const StatItem: React.FC<{ label: string; value: number; color: string }> = ({
  label,
  value,
  color,
}) => (
  <div style={styles.statItem}>
    <span style={{ ...styles.statValue, color }}>{value}</span>
    <span style={styles.statLabel}>{label}</span>
  </div>
);

const Divider: React.FC = () => <div style={styles.divider} />;

const styles: Record<string, React.CSSProperties> = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    background: 'rgba(0,0,0,0.6)',
    backdropFilter: 'blur(12px)',
    border: '1px solid rgba(255,255,255,0.07)',
    borderRadius: 10,
    padding: '6px 16px',
  },
  statItem: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '0 8px',
  },
  statValue: {
    fontSize: 16,
    fontWeight: 700,
    lineHeight: 1.2,
  },
  statLabel: {
    fontSize: 9,
    color: '#475569',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    whiteSpace: 'nowrap',
  },
  divider: {
    width: 1,
    height: 28,
    background: 'rgba(255,255,255,0.08)',
    margin: '0 4px',
  },
};

export default StatsBar;
