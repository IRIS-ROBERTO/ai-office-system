import { formatDuration, taskBucketLabel, taskStatusTone } from './officeUtils';
import type { TaskBucket } from '../../state/officeStore';

interface ControlTowerProps {
  connected: boolean;
  queue: number;
  running: number;
  done: number;
  failed: number;
  blocked: number;
  total: number;
  globalPriority: number;
  activeAgents: number;
  totalAgents: number;
  lastSignal: string | null;
  criticalSlaCount: number;
}

export function ControlTower({
  connected,
  queue,
  running,
  done,
  failed,
  blocked,
  total,
  globalPriority,
  activeAgents,
  totalAgents,
  lastSignal,
  criticalSlaCount,
}: ControlTowerProps) {
  const bucketItems: Array<{ bucket: TaskBucket; value: number }> = [
    { bucket: 'queue', value: queue },
    { bucket: 'running', value: running },
    { bucket: 'done', value: done },
    { bucket: 'failed', value: failed },
  ];

  return (
    <section className="control-tower panel-surface">
      <div className="control-tower__top">
        <div>
          <div className="eyebrow">Control Tower</div>
          <h1 className="shell-title">IRIS AI Office System</h1>
          <p className="shell-copy">
            Orquestração viva do escritório: filas, execução, validação e visão de risco em tempo real.
          </p>
        </div>

        <div className="control-tower__meta">
          <span className={`status-chip ${connected ? 'status-chip--live' : 'status-chip--offline'}`}>
            <span className="status-chip__dot" />
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>
          <span className="priority-pill">Global priority P{Math.max(1, globalPriority)}</span>
          <span className="subtle-chip">{activeAgents}/{totalAgents} active</span>
        </div>
      </div>

      <div className="control-tower__metrics">
        {bucketItems.map(({ bucket, value }) => (
          <div key={bucket} className="metric-card">
            <div className="metric-card__value" style={{ color: taskStatusTone(bucket) }}>{value}</div>
            <div className="metric-card__label">{taskBucketLabel(bucket)}</div>
          </div>
        ))}
        <div className="metric-card metric-card--wide">
          <div className="metric-card__value">{blocked}</div>
          <div className="metric-card__label">Blocked</div>
        </div>
        <div className="metric-card metric-card--wide">
          <div className="metric-card__value">{criticalSlaCount}</div>
          <div className="metric-card__label">SLA at risk</div>
        </div>
        <div className="metric-card metric-card--wide">
          <div className="metric-card__value">{total}</div>
          <div className="metric-card__label">Total tasks</div>
        </div>
      </div>

      <div className="control-tower__footer">
        <div className="tower-line">
          <span className="tower-line__label">Last signal</span>
          <strong>{lastSignal ?? 'Awaiting event stream'}</strong>
        </div>
        <div className="tower-line">
          <span className="tower-line__label">Flow pressure</span>
          <strong>{formatDuration(Math.max(queue * 45, running * 25))}</strong>
        </div>
        <div className="tower-line">
          <span className="tower-line__label">Agent load</span>
          <strong>{activeAgents}/{totalAgents}</strong>
        </div>
      </div>
    </section>
  );
}

export default ControlTower;
