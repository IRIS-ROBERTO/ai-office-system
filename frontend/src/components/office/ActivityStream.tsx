import { useEffect, useRef, useState } from 'react';
import { useOfficeStore } from '../../state/officeStore';
import { formatTimestamp } from './officeUtils';

interface StreamItem {
  id: string;
  message: string;
  tone: string;
  timestamp: number;
}

const MAX_ITEMS = 18;

function eventToItem(payload: Record<string, unknown>): StreamItem | null {
  const type = String(payload.event_type || '');
  const agent = String(payload.agent_id || payload.id || 'agent');
  const task = String(payload.task_id || '');
  const base = task ? `${type} · ${task.slice(0, 8)}` : type;

  const map: Record<string, { message: string; tone: string }> = {
    agent_called: { message: `${agent} entered the flow`, tone: '#fbbf24' },
    agent_thinking: { message: `${agent} is thinking`, tone: '#f59e0b' },
    agent_moving: { message: `${agent} moved across the floor`, tone: '#60a5fa' },
    agent_idle: { message: `${agent} returned to lounge`, tone: '#64748b' },
    task_created: { message: `Task queued ${task.slice(0, 8)}`, tone: '#a855f7' },
    task_assigned: { message: `Task assigned to ${agent}`, tone: '#818cf8' },
    task_started: { message: `Task started ${task.slice(0, 8)}`, tone: '#f59e0b' },
    task_in_progress: { message: `Task running ${task.slice(0, 8)}`, tone: '#f59e0b' },
    task_completed: { message: `Task completed ${task.slice(0, 8)}`, tone: '#22c55e' },
    task_failed: { message: `Task failed ${task.slice(0, 8)}`, tone: '#ef4444' },
    task_blocked: { message: `Task blocked ${task.slice(0, 8)}`, tone: '#f97316' },
  };

  const entry = map[type];
  if (!entry) return null;

  const ts = typeof payload.timestamp === 'string' ? Date.parse(payload.timestamp) : Date.now();
  return {
    id: `${type}-${Math.random()}`,
    message: payload.payload && typeof payload.payload === 'object' && payload.payload !== null && typeof (payload.payload as Record<string, unknown>).subtask_title === 'string'
      ? `${entry.message} · ${(payload.payload as Record<string, unknown>).subtask_title as string}`
      : `${entry.message} · ${base}`,
    tone: entry.tone,
    timestamp: Number.isNaN(ts) ? Date.now() : ts,
  };
}

export function ActivityStream() {
  const [items, setItems] = useState<StreamItem[]>([]);
  const prevQueueLen = useRef(0);

  useEffect(() => {
    const unsubscribe = useOfficeStore.subscribe((state) => {
      const queue = state.animationQueue;
      if (queue.length > prevQueueLen.current) {
        const next = queue.slice(prevQueueLen.current);
        const mapped = next.map((item) => eventToItem(item.payload)).filter(Boolean) as StreamItem[];
        if (mapped.length > 0) {
          setItems((prev) => [...mapped.reverse(), ...prev].slice(0, MAX_ITEMS));
        }
      }
      prevQueueLen.current = queue.length;
    });

    return unsubscribe;
  }, []);

  return (
    <section className="activity-stream panel-surface">
      <div className="activity-stream__header">
        <div>
          <div className="eyebrow">Event Stream</div>
          <h3 className="shell-subtitle">Live runtime signals</h3>
        </div>
        <span className="subtle-chip">{items.length} events</span>
      </div>

      <div className="activity-stream__list">
        {items.length === 0 ? (
          <div className="activity-stream__empty">Waiting for the next runtime event…</div>
        ) : (
          items.map((item) => (
            <div key={item.id} className="activity-row" style={{ borderColor: `${item.tone}44` }}>
              <span className="activity-row__dot" style={{ background: item.tone }} />
              <div className="activity-row__body">
                <strong>{item.message}</strong>
                <small>{formatTimestamp(item.timestamp)}</small>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

export default ActivityStream;
