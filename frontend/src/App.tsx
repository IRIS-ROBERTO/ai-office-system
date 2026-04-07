import React, { useState, useCallback } from 'react';
import { OfficeLayout } from './engine/OfficeLayout';
import { useEventStream } from './websocket/useEventStream';
import { AgentPanel } from './components/ui/AgentPanel';
import { ConnectionStatus } from './components/ui/ConnectionStatus';
import { StatsBar } from './components/ui/StatsBar';
import { useOfficeStore } from './state/officeStore';

export default function App() {
  const { connected } = useEventStream();
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const agents = useOfficeStore((s) => s.agents);

  const handleAgentClick = useCallback((agentId: string) => {
    setSelectedAgentId((prev) => (prev === agentId ? null : agentId));
  }, []);

  const handleClosePanel = useCallback(() => {
    setSelectedAgentId(null);
  }, []);

  const agentCount = Object.keys(agents).length;

  return (
    <div style={styles.root}>
      {/* Canvas engine */}
      <div style={styles.canvasWrapper}>
        <OfficeLayout onAgentClick={handleAgentClick} />
      </div>

      {/* Top HUD bar */}
      <div style={styles.hud}>
        <div style={styles.hudLeft}>
          <div style={styles.logo}>
            <span style={styles.logoIcon}>◈</span>
            <span style={styles.logoText}>AI Office</span>
          </div>
          <ConnectionStatus connected={connected} />
        </div>
        <div style={styles.hudCenter}>
          <StatsBar />
        </div>
        <div style={styles.hudRight}>
          <span style={styles.agentCount}>{agentCount} agents</span>
        </div>
      </div>

      {/* Agent detail panel (glass morphism overlay) */}
      {selectedAgentId && (
        <AgentPanel agentId={selectedAgentId} onClose={handleClosePanel} />
      )}

      {/* Empty state hint when no agents */}
      {agentCount === 0 && (
        <div style={styles.emptyState}>
          <div style={styles.emptyIcon}>◌</div>
          <div style={styles.emptyTitle}>Waiting for agents…</div>
          <div style={styles.emptySubtitle}>
            Connect the backend at <code style={styles.code}>ws://localhost:8000/ws</code>
          </div>
          <div style={styles.emptyHint}>
            {connected
              ? 'WebSocket connected — awaiting agent_registered events'
              : 'WebSocket disconnected — attempting reconnection…'}
          </div>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  root: {
    width: '100vw',
    height: '100vh',
    background: '#0a0a0f',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    overflow: 'hidden',
  },
  canvasWrapper: {
    position: 'relative',
    lineHeight: 0, // Remove inline gap under canvas
  },
  hud: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    height: 52,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 20px',
    background: 'rgba(5, 5, 15, 0.75)',
    backdropFilter: 'blur(14px)',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
    zIndex: 50,
    gap: 12,
  },
  hudLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 14,
    flex: 1,
  },
  hudCenter: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flex: 2,
  },
  hudRight: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
    flex: 1,
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  logoIcon: {
    fontSize: 20,
    color: '#fbbf24',
    lineHeight: 1,
  },
  logoText: {
    fontSize: 14,
    fontWeight: 700,
    color: '#f1f5f9',
    letterSpacing: 0.5,
    whiteSpace: 'nowrap',
  },
  agentCount: {
    fontSize: 11,
    color: '#475569',
    fontFamily: 'monospace',
    letterSpacing: 0.5,
  },
  emptyState: {
    position: 'fixed',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    textAlign: 'center',
    color: '#e2e8f0',
    pointerEvents: 'none',
    zIndex: 10,
  },
  emptyIcon: {
    fontSize: 56,
    color: '#1e3a5f',
    marginBottom: 16,
    animation: 'spin 6s linear infinite',
  },
  emptyTitle: {
    fontSize: 22,
    fontWeight: 700,
    color: '#475569',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 13,
    color: '#334155',
    marginBottom: 6,
  },
  code: {
    background: 'rgba(255,255,255,0.06)',
    padding: '1px 6px',
    borderRadius: 4,
    fontFamily: 'monospace',
    color: '#94a3b8',
  },
  emptyHint: {
    fontSize: 11,
    color: '#1e3a5f',
    marginTop: 8,
    fontStyle: 'italic',
  },
};
