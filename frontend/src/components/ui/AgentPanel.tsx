import React, { useCallback } from 'react';
import { useOfficeStore } from '../../state/officeStore';

interface AgentPanelProps {
  agentId: string | null;
  onClose: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  idle: 'Idle',
  thinking: 'Thinking…',
  working: 'Working',
  moving: 'Moving',
};

const STATUS_COLORS: Record<string, string> = {
  idle: '#94a3b8',
  thinking: '#a855f7',
  working: '#22c55e',
  moving: '#3b82f6',
};

const TASK_STATUS_COLORS: Record<string, string> = {
  pending: '#6b7280',
  assigned: '#3b82f6',
  in_progress: '#f59e0b',
  completed: '#22c55e',
  failed: '#ef4444',
};

export const AgentPanel: React.FC<AgentPanelProps> = ({ agentId, onClose }) => {
  const agent = useOfficeStore((s) => (agentId ? s.agents[agentId] : null));
  const tasks = useOfficeStore((s) => s.tasks);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose]
  );

  if (!agentId || !agent) return null;

  const currentTask = agent.current_task_id ? tasks[agent.current_task_id] : null;

  const completedTasks = Object.values(tasks).filter(
    (t) => t.assigned_agent_id === agentId && t.status === 'completed'
  );
  const allAgentTasks = Object.values(tasks).filter(
    (t) => t.assigned_agent_id === agentId
  );

  return (
    <div
      style={styles.backdrop}
      onClick={handleBackdropClick}
    >
      <div style={styles.panel}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.headerLeft}>
            <div
              style={{
                ...styles.colorDot,
                backgroundColor: agent.color,
                boxShadow: `0 0 10px ${agent.color}88`,
              }}
            />
            <div>
              <div style={styles.agentRole}>{agent.agent_role}</div>
              <div style={styles.agentId}>{agent.agent_id}</div>
            </div>
          </div>
          <button style={styles.closeBtn} onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        {/* Status row */}
        <div style={styles.statusRow}>
          <span style={styles.label}>Status</span>
          <span
            style={{
              ...styles.statusBadge,
              color: STATUS_COLORS[agent.status] || '#94a3b8',
              borderColor: STATUS_COLORS[agent.status] || '#94a3b8',
            }}
          >
            <span style={{
              ...styles.statusDot,
              backgroundColor: STATUS_COLORS[agent.status] || '#94a3b8',
            }} />
            {STATUS_LABELS[agent.status] || agent.status}
          </span>
        </div>

        {/* Team */}
        <div style={styles.infoRow}>
          <span style={styles.label}>Team</span>
          <span style={styles.value}>{agent.team.toUpperCase()}</span>
        </div>

        {/* Position */}
        <div style={styles.infoRow}>
          <span style={styles.label}>Position</span>
          <span style={styles.value}>
            x: {Math.round(agent.position.x)}, y: {Math.round(agent.position.y)}
          </span>
        </div>

        {/* Divider */}
        <div style={styles.divider} />

        {/* Current task */}
        <div style={styles.sectionTitle}>Current Task</div>
        {currentTask ? (
          <div style={styles.taskCard}>
            <div style={styles.taskIdRow}>
              <span style={styles.taskIdText}>{currentTask.task_id.slice(0, 16)}…</span>
              <span
                style={{
                  ...styles.taskStatusBadge,
                  color: TASK_STATUS_COLORS[currentTask.status] || '#94a3b8',
                }}
              >
                {currentTask.status.replace('_', ' ')}
              </span>
            </div>
            <div style={styles.taskRequest}>{currentTask.request || '(no description)'}</div>
          </div>
        ) : (
          <div style={styles.noTask}>No active task</div>
        )}

        {/* Divider */}
        <div style={styles.divider} />

        {/* Stats */}
        <div style={styles.statsRow}>
          <div style={styles.statBlock}>
            <div style={styles.statValue}>{completedTasks.length}</div>
            <div style={styles.statLabel}>Completed</div>
          </div>
          <div style={styles.statBlock}>
            <div style={styles.statValue}>{allAgentTasks.length}</div>
            <div style={styles.statLabel}>Total Tasks</div>
          </div>
          <div style={styles.statBlock}>
            <div style={styles.statValue}>
              {allAgentTasks.length > 0
                ? Math.round((completedTasks.length / allAgentTasks.length) * 100)
                : 0}%
            </div>
            <div style={styles.statLabel}>Success Rate</div>
          </div>
        </div>

        {/* Task history */}
        {allAgentTasks.length > 0 && (
          <>
            <div style={styles.divider} />
            <div style={styles.sectionTitle}>Task History</div>
            <div style={styles.taskList}>
              {allAgentTasks.slice(-5).reverse().map((t) => (
                <div key={t.task_id} style={styles.taskHistoryItem}>
                  <span
                    style={{
                      ...styles.taskHistoryDot,
                      backgroundColor: TASK_STATUS_COLORS[t.status] || '#94a3b8',
                    }}
                  />
                  <span style={styles.taskHistoryText}>
                    {t.request.slice(0, 32)}{t.request.length > 32 ? '…' : ''}
                  </span>
                  <span
                    style={{
                      ...styles.taskHistoryStatus,
                      color: TASK_STATUS_COLORS[t.status] || '#94a3b8',
                    }}
                  >
                    {t.status}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  backdrop: {
    position: 'fixed',
    inset: 0,
    zIndex: 100,
    pointerEvents: 'none',
  },
  panel: {
    position: 'absolute',
    top: '50%',
    right: 24,
    transform: 'translateY(-50%)',
    width: 300,
    maxHeight: '80vh',
    overflowY: 'auto',
    background: 'rgba(10, 10, 20, 0.92)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 14,
    padding: '20px 18px',
    color: '#e2e8f0',
    boxShadow: '0 8px 40px rgba(0,0,0,0.7)',
    pointerEvents: 'all',
    scrollbarWidth: 'thin',
    scrollbarColor: 'rgba(255,255,255,0.15) transparent',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  colorDot: {
    width: 36,
    height: 36,
    borderRadius: '50%',
    flexShrink: 0,
  },
  agentRole: {
    fontSize: 16,
    fontWeight: 700,
    letterSpacing: 0.5,
    textTransform: 'capitalize',
  },
  agentId: {
    fontSize: 10,
    color: '#64748b',
    fontFamily: 'monospace',
    marginTop: 2,
  },
  closeBtn: {
    background: 'rgba(255,255,255,0.08)',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: 8,
    color: '#94a3b8',
    cursor: 'pointer',
    fontSize: 13,
    width: 28,
    height: 28,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    transition: 'background 0.15s',
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  infoRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  label: {
    fontSize: 11,
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  value: {
    fontSize: 12,
    color: '#cbd5e1',
    fontFamily: 'monospace',
  },
  statusBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 12,
    fontWeight: 600,
    border: '1px solid',
    borderRadius: 20,
    padding: '2px 10px',
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: '50%',
    flexShrink: 0,
  },
  divider: {
    height: 1,
    background: 'rgba(255,255,255,0.07)',
    margin: '14px 0',
  },
  sectionTitle: {
    fontSize: 10,
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 10,
  },
  taskCard: {
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 8,
    padding: '10px 12px',
  },
  taskIdRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  taskIdText: {
    fontSize: 9,
    color: '#475569',
    fontFamily: 'monospace',
  },
  taskStatusBadge: {
    fontSize: 10,
    fontWeight: 600,
    textTransform: 'capitalize',
  },
  taskRequest: {
    fontSize: 12,
    color: '#cbd5e1',
    lineHeight: 1.5,
  },
  noTask: {
    fontSize: 12,
    color: '#475569',
    fontStyle: 'italic',
    textAlign: 'center',
    padding: '8px 0',
  },
  statsRow: {
    display: 'flex',
    justifyContent: 'space-around',
    textAlign: 'center',
  },
  statBlock: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 4,
  },
  statValue: {
    fontSize: 22,
    fontWeight: 700,
    color: '#f1f5f9',
  },
  statLabel: {
    fontSize: 9,
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  taskList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  taskHistoryItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    background: 'rgba(255,255,255,0.03)',
    borderRadius: 6,
    padding: '5px 8px',
  },
  taskHistoryDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    flexShrink: 0,
  },
  taskHistoryText: {
    fontSize: 11,
    color: '#94a3b8',
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  taskHistoryStatus: {
    fontSize: 10,
    fontWeight: 600,
    textTransform: 'capitalize',
    flexShrink: 0,
  },
};

export default AgentPanel;
