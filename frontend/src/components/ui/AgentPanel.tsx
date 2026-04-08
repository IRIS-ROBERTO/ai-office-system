import React, { useCallback } from 'react';
import { getAgentProfile } from '../../data/agentProfiles';
import { useOfficeStore } from '../../state/officeStore';

interface AgentPanelProps {
  agentId: string | null;
  onClose: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  idle: 'Idle',
  thinking: 'Thinking',
  working: 'Working',
  moving: 'Moving',
};

const STATUS_COLORS: Record<string, string> = {
  idle: '#94a3b8',
  thinking: '#f59e0b',
  working: '#22c55e',
  moving: '#3b82f6',
};

const TASK_STATUS_COLORS: Record<string, string> = {
  pending: '#6b7280',
  assigned: '#6366f1',
  in_progress: '#f59e0b',
  completed: '#22c55e',
  failed: '#ef4444',
};

const panelStyles: Record<string, React.CSSProperties> = {
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
    width: 380,
    maxHeight: '84vh',
    overflowY: 'auto',
    background: 'linear-gradient(180deg, rgba(7,10,20,0.96) 0%, rgba(10,10,20,0.94) 100%)',
    backdropFilter: 'blur(18px)',
    WebkitBackdropFilter: 'blur(18px)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 18,
    padding: '20px 18px 18px',
    color: '#e2e8f0',
    boxShadow: '0 18px 60px rgba(0,0,0,0.6)',
    pointerEvents: 'all',
    scrollbarWidth: 'thin',
    scrollbarColor: 'rgba(255,255,255,0.14) transparent',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 16,
  },
  identityBlock: {
    display: 'flex',
    gap: 14,
    flex: 1,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 16,
    flexShrink: 0,
    marginTop: 2,
  },
  codename: {
    fontSize: 22,
    fontWeight: 800,
    letterSpacing: 1.6,
    lineHeight: 1,
  },
  title: {
    fontSize: 11,
    color: '#cbd5e1',
    letterSpacing: 0.7,
    textTransform: 'uppercase',
    marginTop: 6,
  },
  roleLine: {
    fontSize: 10,
    color: '#64748b',
    fontFamily: 'monospace',
    marginTop: 6,
  },
  closeBtn: {
    width: 30,
    height: 30,
    borderRadius: 10,
    border: '1px solid rgba(255,255,255,0.12)',
    background: 'rgba(255,255,255,0.04)',
    color: '#94a3b8',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroCard: {
    marginTop: 18,
    padding: '14px 14px 12px',
    borderRadius: 14,
    border: '1px solid rgba(255,255,255,0.07)',
    background: 'rgba(255,255,255,0.035)',
  },
  summary: {
    fontSize: 13,
    lineHeight: 1.65,
    color: '#dbe4f0',
  },
  mission: {
    fontSize: 11,
    color: '#94a3b8',
    lineHeight: 1.6,
    marginTop: 10,
  },
  signature: {
    marginTop: 10,
    fontSize: 11,
    color: '#e2e8f0',
    fontStyle: 'italic',
  },
  statusStrip: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 10,
    marginTop: 16,
  },
  statusCard: {
    borderRadius: 12,
    padding: '12px 12px 10px',
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.06)',
  },
  statusLabel: {
    fontSize: 9,
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: 1.1,
    marginBottom: 8,
  },
  statusValue: {
    fontSize: 12,
    color: '#e2e8f0',
    fontWeight: 700,
  },
  statusBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 7,
    fontSize: 11,
    padding: '4px 10px',
    borderRadius: 999,
    border: '1px solid',
    marginTop: 2,
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: '50%',
    flexShrink: 0,
  },
  section: {
    marginTop: 18,
  },
  sectionTitle: {
    fontSize: 10,
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: 1.4,
    marginBottom: 10,
  },
  chipRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    fontSize: 10,
    color: '#dbe4f0',
    padding: '5px 10px',
    borderRadius: 999,
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.07)',
  },
  statGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
    gap: 10,
  },
  statCard: {
    textAlign: 'center',
    padding: '12px 8px',
    borderRadius: 12,
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.06)',
  },
  statValue: {
    fontSize: 22,
    fontWeight: 800,
    color: '#f8fafc',
    lineHeight: 1,
  },
  statCaption: {
    marginTop: 6,
    fontSize: 9,
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: 0.7,
  },
  taskCard: {
    padding: '12px 14px',
    borderRadius: 14,
    background: 'rgba(255,255,255,0.035)',
    border: '1px solid rgba(255,255,255,0.07)',
  },
  taskTopRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
    marginBottom: 8,
  },
  taskId: {
    fontSize: 10,
    color: '#64748b',
    fontFamily: 'monospace',
  },
  taskRequest: {
    fontSize: 12,
    color: '#dbe4f0',
    lineHeight: 1.55,
  },
  badge: {
    fontSize: 10,
    fontWeight: 700,
    textTransform: 'capitalize',
  },
  timeline: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  timelineItem: {
    display: 'grid',
    gridTemplateColumns: '10px 1fr',
    gap: 10,
    padding: '10px 10px 10px 0',
    borderBottom: '1px solid rgba(255,255,255,0.05)',
  },
  timelineDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    marginTop: 5,
  },
  timelineMessage: {
    fontSize: 11,
    color: '#dbe4f0',
    lineHeight: 1.5,
  },
  timelineMeta: {
    marginTop: 4,
    fontSize: 9,
    color: '#64748b',
    fontFamily: 'monospace',
    display: 'flex',
    gap: 10,
    flexWrap: 'wrap',
  },
  noState: {
    fontSize: 12,
    color: '#64748b',
    fontStyle: 'italic',
    textAlign: 'center',
    padding: '8px 0',
  },
  bulletList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  bulletItem: {
    fontSize: 11,
    color: '#cbd5e1',
    lineHeight: 1.5,
    paddingLeft: 14,
    position: 'relative',
  },
};

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function RuntimeTimeline({ items }: { items: Array<{ id: string; message: string; timestamp: number; task_id: string | null; tone: string }> }) {
  if (items.length === 0) {
    return <div style={panelStyles.noState}>No runtime activity recorded yet.</div>;
  }

  return (
    <div style={panelStyles.timeline}>
      {items.map((item) => (
        <div key={item.id} style={panelStyles.timelineItem}>
          <div style={{ ...panelStyles.timelineDot, background: item.tone, boxShadow: `0 0 12px ${item.tone}55` }} />
          <div>
            <div style={panelStyles.timelineMessage}>{item.message}</div>
            <div style={panelStyles.timelineMeta}>
              <span>{formatTime(item.timestamp)}</span>
              {item.task_id ? <span>{item.task_id.slice(0, 12)}…</span> : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export const AgentPanel: React.FC<AgentPanelProps> = ({ agentId, onClose }) => {
  const agent = useOfficeStore((s) => (agentId ? s.agents[agentId] : null));
  const tasks = useOfficeStore((s) => s.tasks);
  const activity = useOfficeStore((s) => (agentId ? s.agentActivity[agentId] || [] : []));

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose]
  );

  if (!agentId || !agent) return null;

  const profile = getAgentProfile(agent.agent_id, agent.agent_role);
  const currentTask = agent.current_task_id ? tasks[agent.current_task_id] : null;
  const allAgentTasks = Object.values(tasks).filter((task) => task.assigned_agent_id === agentId);
  const completedTasks = allAgentTasks.filter((task) => task.status === 'completed');
  const successRate = allAgentTasks.length > 0
    ? Math.round((completedTasks.length / allAgentTasks.length) * 100)
    : 100;
  const latestActivity = activity[0];
  const headerGlow = `${agent.color}33`;

  return (
    <div style={panelStyles.backdrop} onClick={handleBackdropClick}>
      <div style={{ ...panelStyles.panel, borderColor: headerGlow }}>
        <div style={panelStyles.header}>
          <div style={panelStyles.identityBlock}>
            <div
              style={{
                ...panelStyles.avatar,
                background: `linear-gradient(145deg, ${agent.color}, rgba(255,255,255,0.08))`,
                boxShadow: `0 0 22px ${headerGlow}`,
              }}
            />
            <div style={{ flex: 1 }}>
              <div style={{ ...panelStyles.codename, color: agent.color }}>{profile.codename}</div>
              <div style={panelStyles.title}>{profile.title}</div>
              <div style={panelStyles.roleLine}>
                {agent.team.toUpperCase()} / {agent.agent_role} / {agent.agent_id}
              </div>
            </div>
          </div>
          <button style={panelStyles.closeBtn} onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div style={{ ...panelStyles.heroCard, borderColor: `${agent.color}26` }}>
          <div style={panelStyles.summary}>{profile.summary}</div>
          <div style={panelStyles.mission}><strong style={{ color: '#e2e8f0' }}>Mission:</strong> {profile.mission}</div>
          <div style={panelStyles.signature}>“{profile.signature}”</div>
        </div>

        <div style={panelStyles.statusStrip}>
          <div style={panelStyles.statusCard}>
            <div style={panelStyles.statusLabel}>Live Status</div>
            <div
              style={{
                ...panelStyles.statusBadge,
                color: STATUS_COLORS[agent.status] || '#94a3b8',
                borderColor: STATUS_COLORS[agent.status] || '#94a3b8',
              }}
            >
              <span style={{ ...panelStyles.statusDot, backgroundColor: STATUS_COLORS[agent.status] || '#94a3b8' }} />
              {STATUS_LABELS[agent.status] || agent.status}
            </div>
          </div>
          <div style={panelStyles.statusCard}>
            <div style={panelStyles.statusLabel}>Last Signal</div>
            <div style={panelStyles.statusValue}>
              {latestActivity ? latestActivity.message : 'Profile loaded and awaiting work'}
            </div>
          </div>
        </div>

        <div style={panelStyles.section}>
          <div style={panelStyles.sectionTitle}>Personality Matrix</div>
          <div style={panelStyles.chipRow}>
            {profile.personality.map((trait) => (
              <span key={trait} style={{ ...panelStyles.chip, borderColor: `${agent.color}22` }}>{trait}</span>
            ))}
          </div>
        </div>

        <div style={panelStyles.section}>
          <div style={panelStyles.sectionTitle}>Strengths & Toolkit</div>
          <div style={panelStyles.chipRow}>
            {profile.strengths.map((strength) => (
              <span key={strength} style={panelStyles.chip}>{strength}</span>
            ))}
            {profile.toolkit.map((tool) => (
              <span key={tool} style={{ ...panelStyles.chip, color: '#94a3b8' }}>{tool}</span>
            ))}
          </div>
        </div>

        <div style={panelStyles.section}>
          <div style={panelStyles.sectionTitle}>Professional Snapshot</div>
          <div style={panelStyles.taskCard}>
            <div style={panelStyles.taskRequest}>{profile.experience}</div>
          </div>
        </div>

        <div style={panelStyles.section}>
          <div style={panelStyles.sectionTitle}>Performance Ledger</div>
          <div style={panelStyles.statGrid}>
            <div style={panelStyles.statCard}>
              <div style={{ ...panelStyles.statValue, color: '#22c55e' }}>{agent.completed_tasks}</div>
              <div style={panelStyles.statCaption}>Completed</div>
            </div>
            <div style={panelStyles.statCard}>
              <div style={panelStyles.statValue}>{allAgentTasks.length}</div>
              <div style={panelStyles.statCaption}>Tracked</div>
            </div>
            <div style={panelStyles.statCard}>
              <div style={{ ...panelStyles.statValue, color: '#fbbf24' }}>{successRate}%</div>
              <div style={panelStyles.statCaption}>Success</div>
            </div>
            <div style={panelStyles.statCard}>
              <div style={{ ...panelStyles.statValue, color: agent.error_count > 0 ? '#ef4444' : '#94a3b8' }}>
                {agent.error_count}
              </div>
              <div style={panelStyles.statCaption}>Errors</div>
            </div>
          </div>
        </div>

        <div style={panelStyles.section}>
          <div style={panelStyles.sectionTitle}>Current Assignment</div>
          {currentTask ? (
            <div style={panelStyles.taskCard}>
              <div style={panelStyles.taskTopRow}>
                <span style={panelStyles.taskId}>{currentTask.task_id.slice(0, 16)}…</span>
                <span
                  style={{
                    ...panelStyles.badge,
                    color: TASK_STATUS_COLORS[currentTask.status] || '#94a3b8',
                  }}
                >
                  {currentTask.status.replace('_', ' ')}
                </span>
              </div>
              <div style={panelStyles.taskRequest}>{currentTask.request || '(no description)'}</div>
            </div>
          ) : (
            <div style={panelStyles.noState}>No active task at the moment.</div>
          )}
        </div>

        <div style={panelStyles.section}>
          <div style={panelStyles.sectionTitle}>Career Highlights</div>
          <div style={panelStyles.bulletList}>
            {profile.careerHighlights.map((item) => (
              <div key={item} style={panelStyles.bulletItem}>
                <span style={{ position: 'absolute', left: 0, color: agent.color }}>•</span>
                {item}
              </div>
            ))}
          </div>
        </div>

        <div style={panelStyles.section}>
          <div style={panelStyles.sectionTitle}>Runtime Timeline</div>
          <RuntimeTimeline items={activity} />
        </div>
      </div>
    </div>
  );
};

export default AgentPanel;
