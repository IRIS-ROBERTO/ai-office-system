/**
 * ActivityFeed — Live event stream panel
 * Subscribes to the Zustand animationQueue to display real-time events.
 * Newest items appear at top. Max 60 items retained.
 */
import React, { useEffect, useRef, useState } from 'react';
import { useOfficeStore } from '../../state/officeStore';

interface FeedItem {
  id: string;
  type: string;
  message: string;
  timestamp: number;
  color: string;
  icon: string;
}

// Map raw event_type + payload → display config
function eventToItem(payload: Record<string, unknown>): FeedItem | null {
  const type = (payload.event_type as string) || '';
  const agentId  = ((payload.agent_id  || payload.id)    as string | undefined)?.slice(0, 8) ?? '—';
  const role     = (payload.agent_role || payload.role    || '') as string;
  const eventPayload = (payload.payload as Record<string, unknown> | undefined) || {};
  const taskId   = ((payload.task_id   as string) || '').slice(0, 8);
  const name     = role ? role : agentId;

  const MAP: Record<string, { msg: string; color: string; icon: string }> = {
    agent_registered:    { msg: `"${name}" joined`,          color: '#00c8ff', icon: '▶' },
    agent_created:       { msg: `"${name}" spawned`,         color: '#00c8ff', icon: '⊕' },
    agent_status_changed:{ msg: `${name} → ${payload.status}`, color: '#64748b', icon: '◉' },
    agent_called:        { msg: `${name} called`,             color: '#fbbf24', icon: '◎' },
    agent_assigned:      { msg: `${name} assigned`,           color: '#6366f1', icon: '⇒' },
    agent_thinking:      { msg: `${name} thinking…`,          color: '#fbbf24', icon: '◌' },
    agent_idle:          { msg: `${name} idle`,               color: '#64748b', icon: '·' },
    agent_moving:        { msg: `${name} moving`,             color: '#3b82f6', icon: '⇢' },
    agent_moved:         { msg: `${name} moved`,               color: '#3b82f6', icon: '⇒' },
    task_created:        { msg: `Task created  [${taskId}…]`,  color: '#a855f7', icon: '✦' },
    task_assigned:       { msg: `Task [${taskId}…] → ${name}`, color: '#6366f1', icon: '⇒' },
    task_started:        { msg: `Task [${taskId}…] started`,   color: '#f59e0b', icon: '▷' },
    task_in_progress:    { msg: `Task [${taskId}…] in progress`, color: '#f59e0b', icon: '⋯' },
    task_heartbeat:      { msg: `Task [${taskId}…] still running`, color: '#38bdf8', icon: '⏱' },
    task_completed:      { msg: `Task [${taskId}…] done`,      color: '#00ff88', icon: '✓' },
    task_failed:         { msg: `Task [${taskId}…] failed`,    color: '#ef4444', icon: '✗' },
    git_commit:          { msg: `${name} committed ${String(eventPayload.sha || '').slice(0, 8)}`, color: '#22c55e', icon: '◆' },
    git_push:            { msg: `${name} pushed ${String(eventPayload.sha || '').slice(0, 8)}`, color: '#00ff88', icon: '↑' },
    commit_failed:       { msg: `${name} commit evidence failed`, color: '#ef4444', icon: '!' },
  };

  const cfg = MAP[type];
  if (!cfg) return null;

  return {
    id: `${Date.now()}-${Math.random()}`,
    type,
    message: eventPayload.subtask_title
      ? `${cfg.msg} • ${String(eventPayload.subtask_title)}`
      : cfg.msg,
    timestamp: Date.now(),
    color: cfg.color,
    icon: cfg.icon,
  };
}

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('en-US', {
    hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

const MAX_ITEMS = 60;

export const ActivityFeed: React.FC = () => {
  const [items, setItems] = useState<FeedItem[]>([]);
  const prevQueueLen = useRef(0);

  useEffect(() => {
    // Subscribe to animationQueue length changes to extract new events
    const unsub = useOfficeStore.subscribe((state) => {
      const q = state.animationQueue;
      if (q.length > prevQueueLen.current) {
        // Collect all new items added since last check
        const newRaw = q.slice(prevQueueLen.current);
        const newItems: FeedItem[] = [];
        for (const raw of newRaw) {
          const item = eventToItem(raw.payload as Record<string, unknown>);
          if (item) newItems.push(item);
        }
        if (newItems.length > 0) {
          setItems(prev => [...newItems.reverse(), ...prev].slice(0, MAX_ITEMS));
        }
      }
      prevQueueLen.current = q.length;
    });
    return unsub;
  }, []);

  return (
    <div style={{
      flex: 1, overflowY: 'auto', padding: '6px 8px',
      display: 'flex', flexDirection: 'column', gap: 3,
      scrollbarWidth: 'thin',
      scrollbarColor: 'rgba(255,255,255,0.06) transparent',
    }}>
      {items.length === 0 ? (
        <div style={{
          textAlign: 'center', color: 'rgba(255,255,255,0.15)',
          fontSize: 10, marginTop: 20, fontStyle: 'italic', padding: '0 8px',
        }}>
          Waiting for events…
        </div>
      ) : (
        items.map(item => (
          <FeedRow key={item.id} item={item} />
        ))
      )}
    </div>
  );
};

const FeedRow: React.FC<{ item: FeedItem }> = ({ item }) => (
  <div style={{
    display: 'flex', alignItems: 'flex-start', gap: 7,
    padding: '5px 8px', borderRadius: 7,
    background: `${item.color}09`,
    borderLeft: `2px solid ${item.color}44`,
    animation: 'feedFadeIn 0.25s ease',
    flexShrink: 0,
  }}>
    <span style={{
      fontSize: 9, color: item.color, fontFamily: 'monospace',
      marginTop: 2, flexShrink: 0, width: 12, textAlign: 'center',
    }}>
      {item.icon}
    </span>
    <div style={{ flex: 1, overflow: 'hidden', minWidth: 0 }}>
      <div style={{
        fontSize: 10, color: 'rgba(226,232,240,0.85)', lineHeight: 1.4,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {item.message}
      </div>
      <div style={{
        fontSize: 8, color: 'rgba(100,116,139,0.7)', fontFamily: 'monospace',
        marginTop: 1, letterSpacing: 0.2,
      }}>
        {fmtTime(item.timestamp)}
      </div>
    </div>

    <style>{`
      @keyframes feedFadeIn {
        from { opacity: 0; transform: translateX(6px); }
        to   { opacity: 1; transform: translateX(0); }
      }
    `}</style>
  </div>
);

export default ActivityFeed;
