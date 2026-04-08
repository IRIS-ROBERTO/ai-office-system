/**
 * IRIS — AI Office System
 * Premium shell: WebGL canvas + glass morphism HUD + live panels
 */
import React, { useState, useCallback, useEffect, useRef } from 'react';
import { OfficeLayout } from './engine/OfficeLayout';
import { useEventStream } from './websocket/useEventStream';
import { AgentPanel } from './components/ui/AgentPanel';
import { ActivityFeed } from './components/ui/ActivityFeed';
import { useOfficeStore } from './state/officeStore';

// ─── Color tokens ─────────────────────────────────────────────────────────────
const C = {
  bg:         '#03030a',
  surface:    'rgba(8, 8, 20, 0.82)',
  border:     'rgba(255, 255, 255, 0.07)',
  borderDev:  'rgba(0, 200, 255, 0.2)',
  borderMkt:  'rgba(177, 68, 255, 0.2)',
  borderGold: 'rgba(251, 191, 36, 0.3)',
  textPrimary:   '#e2e8f0',
  textSecondary: '#64748b',
  textDev:    '#00c8ff',
  textMkt:    '#b144ff',
  textGold:   '#fbbf24',
  green:  '#00ff88',
  red:    '#ef4444',
  yellow: '#fbbf24',
};

// ─── Utility: Status color ────────────────────────────────────────────────────
function statusColor(s: string) {
  switch (s) {
    case 'working':  return C.green;
    case 'thinking': return C.yellow;
    case 'moving':   return C.textDev;
    case 'idle':     return C.textSecondary;
    default:         return C.textSecondary;
  }
}

// ─── Sub-component: Connection indicator ──────────────────────────────────────
const ConnectionDot: React.FC<{ connected: boolean }> = ({ connected }) => {
  const [pulse, setPulse] = useState(false);
  useEffect(() => {
    if (!connected) return;
    const id = setInterval(() => setPulse(p => !p), 1400);
    return () => clearInterval(id);
  }, [connected]);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        background: connected ? C.green : C.red,
        boxShadow: connected && pulse ? `0 0 10px ${C.green}` : 'none',
        transition: 'box-shadow 0.4s',
        flexShrink: 0,
      }} />
      <span style={{ fontSize: 11, color: connected ? C.green : C.red, fontFamily: 'monospace', letterSpacing: 0.5 }}>
        {connected ? 'LIVE' : 'DISCONNECTED'}
      </span>
    </div>
  );
};

// ─── Sub-component: Team stats chip ───────────────────────────────────────────
const TeamChip: React.FC<{
  label: string; count: number; working: number; color: string; border: string;
}> = ({ label, count, working, color, border }) => (
  <div style={{
    display: 'flex', alignItems: 'center', gap: 8,
    background: 'rgba(255,255,255,0.03)',
    border: `1px solid ${border}`,
    borderRadius: 10, padding: '5px 12px', flexShrink: 0,
  }}>
    <span style={{ fontSize: 10, color, fontFamily: 'monospace', letterSpacing: 1, fontWeight: 700 }}>
      {label}
    </span>
    <div style={{ width: 1, height: 14, background: border }} />
    <span style={{ fontSize: 13, fontWeight: 700, color: C.textPrimary }}>{count}</span>
    <span style={{ fontSize: 10, color: C.textSecondary }}>agents</span>
    {working > 0 && (
      <span style={{
        fontSize: 9, background: `${color}22`, color, borderRadius: 4,
        padding: '1px 6px', fontFamily: 'monospace',
      }}>{working} active</span>
    )}
  </div>
);

// ─── Sub-component: Task stats bar ───────────────────────────────────────────
const TaskBar: React.FC = () => {
  const tasks = useOfficeStore(s => s.tasks);
  const arr = Object.values(tasks);
  const pending   = arr.filter(t => t.status === 'pending').length;
  const active    = arr.filter(t => t.status === 'in_progress' || t.status === 'assigned').length;
  const completed = arr.filter(t => t.status === 'completed').length;
  const failed    = arr.filter(t => t.status === 'failed').length;
  const total     = arr.length;

  const items = [
    { label: 'QUEUE',    n: pending,   col: C.textSecondary },
    { label: 'RUNNING',  n: active,    col: C.yellow },
    { label: 'DONE',     n: completed, col: C.green },
    { label: 'FAILED',   n: failed,    col: C.red },
  ];

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      {items.map(({ label, n, col }) => (
        <div key={label} style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          padding: '3px 10px', borderRadius: 8,
          background: n > 0 ? `${col}11` : 'transparent',
          minWidth: 50,
        }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: n > 0 ? col : C.textSecondary,
            lineHeight: 1, fontFamily: 'monospace' }}>{n}</span>
          <span style={{ fontSize: 8, color: C.textSecondary, letterSpacing: 0.8, marginTop: 2 }}>{label}</span>
        </div>
      ))}
      {total > 0 && (
        <>
          <div style={{ width: 1, height: 28, background: C.border, margin: '0 6px' }} />
          <span style={{ fontSize: 10, color: C.textSecondary, fontFamily: 'monospace' }}>
            {total} total
          </span>
        </>
      )}
    </div>
  );
};

// ─── Sub-component: Agent roster sidebar ─────────────────────────────────────
const AgentRoster: React.FC<{ onAgentClick: (id: string) => void; selectedId: string | null }> = ({
  onAgentClick, selectedId
}) => {
  const agents = useOfficeStore(s => s.agents);
  const list = Object.values(agents).sort((a, b) => a.team.localeCompare(b.team));

  if (list.length === 0) return (
    <div style={{ padding: '16px 14px', color: C.textSecondary, fontSize: 11, fontStyle: 'italic', textAlign: 'center' }}>
      No agents connected
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, overflowY: 'auto',
      maxHeight: 'calc(100vh - 260px)', padding: '0 4px', scrollbarWidth: 'thin',
      scrollbarColor: `rgba(255,255,255,0.08) transparent` }}>
      {list.map(agent => {
        const isSelected = agent.agent_id === selectedId;
        const teamColor = agent.team === 'dev' ? C.textDev : C.textMkt;
        return (
          <button
            key={agent.agent_id}
            onClick={() => onAgentClick(agent.agent_id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              background: isSelected ? `${agent.color}18` : 'rgba(255,255,255,0.025)',
              border: `1px solid ${isSelected ? agent.color + '55' : C.border}`,
              borderRadius: 9, padding: '8px 10px', cursor: 'pointer',
              textAlign: 'left', transition: 'all 0.15s',
            }}
          >
            {/* Color dot */}
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: `radial-gradient(circle at 35% 35%, ${agent.color}dd, ${agent.color}66)`,
              boxShadow: `0 0 8px ${agent.color}55`,
              flexShrink: 0,
            }} />
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.textPrimary,
                textTransform: 'capitalize', letterSpacing: 0.3 }}>
                {agent.agent_role}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 2 }}>
                <span style={{ fontSize: 9, color: teamColor, letterSpacing: 0.5, fontFamily: 'monospace' }}>
                  {agent.team.toUpperCase()}
                </span>
                <span style={{ width: 4, height: 4, borderRadius: '50%',
                  background: statusColor(agent.status), display: 'inline-block' }} />
                <span style={{ fontSize: 9, color: statusColor(agent.status), letterSpacing: 0.3 }}>
                  {agent.status}
                </span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
};

// ─── Sub-component: Empty state ───────────────────────────────────────────────
const EmptyState: React.FC<{ connected: boolean }> = ({ connected }) => {
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setFrame(f => (f + 1) % 4), 500);
    return () => clearInterval(id);
  }, []);
  const dots = '.'.repeat(frame + 1);

  return (
    <div style={{
      position: 'fixed', top: '50%', left: '50%',
      transform: 'translate(-50%, -50%)',
      textAlign: 'center', pointerEvents: 'none', zIndex: 10,
    }}>
      <div style={{
        width: 80, height: 80, borderRadius: '50%', margin: '0 auto 20px',
        background: 'radial-gradient(circle, rgba(0,200,255,0.08), transparent)',
        border: '1px solid rgba(0,200,255,0.15)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 36, color: 'rgba(0,200,255,0.3)',
      }}>◎</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'rgba(255,255,255,0.3)', marginBottom: 8 }}>
        {connected ? `Awaiting agents${dots}` : 'Connecting to IRIS backend'}
      </div>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.15)', fontFamily: 'monospace' }}>
        {connected ? 'POST /tasks/dev to start' : (import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws')}
      </div>
      {!connected && (
        <div style={{ marginTop: 16, fontSize: 10, color: 'rgba(251,191,36,0.4)', fontFamily: 'monospace' }}>
          Run IRIS.bat to start the backend
        </div>
      )}
    </div>
  );
};

// ─── Root App ─────────────────────────────────────────────────────────────────
export default function App() {
  const { connected } = useEventStream();
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const agents = useOfficeStore(s => s.agents);
  const agentArr = Object.values(agents);
  const devAgents = agentArr.filter(a => a.team === 'dev');
  const mktAgents = agentArr.filter(a => a.team === 'marketing');
  const devWorking = devAgents.filter(a => a.status === 'working').length;
  const mktWorking = mktAgents.filter(a => a.status === 'working').length;
  const agentCount = agentArr.length;

  const handleAgentClick = useCallback((id: string) => {
    setSelectedAgentId(p => p === id ? null : id);
  }, []);

  const handleClosePanel = useCallback(() => setSelectedAgentId(null), []);

  // Scale canvas to fit viewport
  const [scale, setScale] = useState(1);
  const containerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function resize() {
      const vw = window.innerWidth  - (agentCount > 0 ? 260 : 0);
      const vh = window.innerHeight - 52; // minus top bar
      const CANVAS_W = 1440, CANVAS_H = 810;
      const s = Math.min(vw / CANVAS_W, vh / CANVAS_H, 1);
      setScale(s);
    }
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, [agentCount]);

  return (
    <div style={{ width: '100vw', height: '100vh', background: C.bg,
      display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* ── TOP HUD BAR ──────────────────────────────────────────────────── */}
      <div style={{
        height: 52, flexShrink: 0,
        background: 'rgba(3, 3, 10, 0.9)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderBottom: `1px solid ${C.border}`,
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '0 18px', zIndex: 50,
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexShrink: 0 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, fontWeight: 900, color: '#000', fontFamily: 'monospace',
            boxShadow: '0 0 14px rgba(251,191,36,0.35)',
          }}>◈</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 800, color: C.textPrimary, letterSpacing: 0.5, lineHeight: 1 }}>
              IRIS
            </div>
            <div style={{ fontSize: 8, color: C.textGold, letterSpacing: 2, lineHeight: 1, marginTop: 2 }}>
              AI OFFICE SYSTEM
            </div>
          </div>
        </div>

        <div style={{ width: 1, height: 30, background: C.border, flexShrink: 0 }} />

        {/* Connection */}
        <ConnectionDot connected={connected} />

        <div style={{ width: 1, height: 30, background: C.border, flexShrink: 0 }} />

        {/* Team chips */}
        <TeamChip label="DEV" count={devAgents.length} working={devWorking}
          color={C.textDev} border={C.borderDev} />
        <TeamChip label="MKT" count={mktAgents.length} working={mktWorking}
          color={C.textMkt} border={C.borderMkt} />

        <div style={{ flex: 1 }} />

        {/* Task stats */}
        <TaskBar />

        <div style={{ width: 1, height: 30, background: C.border, flexShrink: 0 }} />

        {/* Scale indicator */}
        <span style={{ fontSize: 10, color: C.textSecondary, fontFamily: 'monospace', flexShrink: 0 }}>
          {agentCount} agent{agentCount !== 1 ? 's' : ''}
        </span>
      </div>

      {/* ── MAIN AREA ────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* Canvas area */}
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: C.bg, position: 'relative', overflow: 'hidden',
        }}>
          {/* Vignette overlay */}
          <div style={{
            position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 1,
            background: 'radial-gradient(ellipse at 50% 50%, transparent 55%, rgba(3,3,10,0.6) 100%)',
          }} />

          <div ref={containerRef} style={{
            transform: `scale(${scale})`, transformOrigin: 'center center',
            lineHeight: 0, position: 'relative',
          }}>
            <OfficeLayout onAgentClick={handleAgentClick} />
          </div>

          {/* Empty state */}
          {agentCount === 0 && <EmptyState connected={connected} />}
        </div>

        {/* ── RIGHT SIDEBAR ─────────────────────────────────────────────── */}
        {agentCount > 0 && (
          <div style={{
            width: 252, flexShrink: 0,
            background: 'rgba(5, 5, 14, 0.92)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            borderLeft: `1px solid ${C.border}`,
            display: 'flex', flexDirection: 'column',
            overflow: 'hidden',
          }}>
            {/* Agents section */}
            <div style={{
              padding: '14px 14px 10px',
              borderBottom: `1px solid ${C.border}`,
            }}>
              <div style={{ fontSize: 9, color: C.textSecondary, letterSpacing: 2,
                textTransform: 'uppercase', marginBottom: 10 }}>
                Active Agents
              </div>
              <AgentRoster onAgentClick={handleAgentClick} selectedId={selectedAgentId} />
            </div>

            {/* Activity Feed */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div style={{ padding: '10px 14px 6px',
                borderBottom: `1px solid ${C.border}` }}>
                <div style={{ fontSize: 9, color: C.textSecondary, letterSpacing: 2, textTransform: 'uppercase' }}>
                  Event Stream
                </div>
              </div>
              <ActivityFeed />
            </div>
          </div>
        )}
      </div>

      {/* ── AGENT DETAIL PANEL (floating) ────────────────────────────────── */}
      {selectedAgentId && (
        <AgentPanel agentId={selectedAgentId} onClose={handleClosePanel} />
      )}
    </div>
  );
}
