import React, { Suspense, useMemo } from 'react';
import type { Agent } from '../../state/officeStore';
import type { ExecutionLogItem, OfficeTask, SystemHealth } from '../../types/operations';
import { formatDateLabel, formatMinutes } from '../../utils/operations';
import { AgentDetailsModal } from '../ops/AgentDetailsModal';
import { TaskNode } from '../ops/TaskNode';

interface CommandCenterProps {
  connected: boolean;
  agents: Agent[];
  tasks: OfficeTask[];
  loading: boolean;
  error: string | null;
  selectedTask: OfficeTask | null;
  selectedLogs: ExecutionLogItem[];
  logsLoading: boolean;
  health: SystemHealth | null;
  selectedAgentId: string | null;
  onSelectTask: (requestId: string) => void;
  onSelectAgent: (agentId: string | null) => void;
  ActivityFeed: React.LazyExoticComponent<React.ComponentType>;
}

interface Metric {
  label: string;
  value: string;
  detail: string;
  tone: 'neutral' | 'good' | 'warn' | 'bad' | 'blue';
}

const taskIsOpen = (task: OfficeTask) => task.status !== 'completed';
const taskIsRunning = (task: OfficeTask) =>
  ['in_execution', 'in_testing', 'awaiting_approval'].includes(task.status);

function percent(value: number): string {
  if (!Number.isFinite(value)) return '0%';
  return `${Math.round(value)}%`;
}

function getToneClass(tone: Metric['tone']) {
  return `metric-strip__item metric-strip__item--${tone}`;
}

function statusTone(task: OfficeTask): 'good' | 'warn' | 'bad' | 'blue' | 'neutral' {
  if (task.status === 'completed') return 'good';
  if (task.status === 'failed' || task.status === 'changes_requested' || task.slaState === 'breached') return 'bad';
  if (task.slaState === 'warning' || task.status === 'awaiting_approval') return 'warn';
  if (taskIsRunning(task)) return 'blue';
  return 'neutral';
}

function healthTone(value?: string | null, persistent?: boolean): 'good' | 'warn' | 'bad' {
  if (!value || value === 'offline') return 'bad';
  if (value === 'degraded_fake' || persistent === false) return 'warn';
  return 'good';
}

function stageProgress(task: OfficeTask): number {
  const completed = task.stages.filter((stage) => stage.state === 'completed').length;
  const active = task.stages.some((stage) => stage.state === 'active') ? 0.5 : 0;
  return Math.min(100, Math.round(((completed + active) / task.stages.length) * 100));
}

function roleLabel(role: string): string {
  return role.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function buildMetrics(tasks: OfficeTask[], agents: Agent[], health: SystemHealth | null): Metric[] {
  const openTasks = tasks.filter(taskIsOpen);
  const running = tasks.filter(taskIsRunning).length;
  const done = tasks.filter((task) => task.status === 'completed').length;
  const failed = tasks.filter((task) => task.status === 'failed' || task.status === 'changes_requested').length;
  const slaRisk = openTasks.filter((task) => task.slaState !== 'healthy').length;
  const avgLeadTime = done > 0
    ? Math.round(tasks.filter((task) => task.status === 'completed').reduce((sum, task) => sum + task.queueMinutes, 0) / done)
    : 0;
  const changeFailureRate = done + failed > 0 ? (failed / (done + failed)) * 100 : 0;
  const activeAgents = agents.filter((agent) => agent.status !== 'idle').length;

  return [
    {
      label: 'Work in progress',
      value: String(running),
      detail: `${openTasks.length} demandas abertas`,
      tone: running > 0 ? 'blue' : 'neutral',
    },
    {
      label: 'SLA at risk',
      value: String(slaRisk),
      detail: 'bloqueios, risco ou prazo estourado',
      tone: slaRisk > 0 ? 'bad' : 'good',
    },
    {
      label: 'Lead time proxy',
      value: avgLeadTime ? formatMinutes(avgLeadTime) : 'sem base',
      detail: 'média das entregas concluídas',
      tone: avgLeadTime > 240 ? 'warn' : 'neutral',
    },
    {
      label: 'Change failure',
      value: percent(changeFailureRate),
      detail: 'changes_requested + failed',
      tone: changeFailureRate > 20 ? 'bad' : changeFailureRate > 0 ? 'warn' : 'good',
    },
    {
      label: 'Agent utilization',
      value: `${activeAgents}/${agents.length || 0}`,
      detail: 'agentes ativos vs registrados',
      tone: activeAgents > 0 ? 'blue' : 'neutral',
    },
    {
      label: 'Event durability',
      value: health?.event_bus_persistent ? 'real' : 'degraded',
      detail: health?.event_bus ?? 'sem health',
      tone: health?.event_bus_persistent ? 'good' : 'warn',
    },
  ];
}

function TeamWorkstream({
  team,
  tasks,
  agents,
  onSelectTask,
}: {
  team: 'dev' | 'marketing';
  tasks: OfficeTask[];
  agents: Agent[];
  onSelectTask: (requestId: string) => void;
}) {
  const teamTasks = tasks.filter((task) => task.team === team);
  const openTasks = teamTasks.filter(taskIsOpen);
  const running = teamTasks.filter(taskIsRunning).length;
  const blocked = teamTasks.filter((task) => task.bottlenecks.length > 0 || task.slaState === 'breached').length;
  const teamAgents = agents.filter((agent) => agent.team === team);
  const activeAgents = teamAgents.filter((agent) => agent.status !== 'idle').length;

  return (
    <section className={`workstream workstream--${team}`}>
      <div className="section-head">
        <div>
          <p className="eyebrow">{team === 'dev' ? 'Dev Delivery' : 'Marketing Revenue Ops'}</p>
          <h2>{team === 'dev' ? 'Build, test, ship' : 'Research, create, distribute'}</h2>
        </div>
        <span className="section-badge">{activeAgents}/{teamAgents.length} ativos</span>
      </div>

      <div className="workstream__stats">
        <Stat label="Abertas" value={openTasks.length} />
        <Stat label="Rodando" value={running} />
        <Stat label="Risco" value={blocked} tone={blocked > 0 ? 'bad' : 'good'} />
      </div>

      <div className="workstream__lane" aria-label={`Demandas do time ${team}`}>
        {teamTasks.slice(0, 5).map((task) => (
          <button
            className={`workstream-task workstream-task--${statusTone(task)}`}
            key={task.requestId}
            onClick={() => onSelectTask(task.requestId)}
          >
            <span className="workstream-task__priority">P{task.priority}</span>
            <span className="workstream-task__main">
              <strong>{task.title}</strong>
              <small>{task.stageLabel} · {task.currentAgentRole ?? 'CROWN'} · {formatMinutes(task.queueMinutes)}</small>
            </span>
            <span className="workstream-task__progress" aria-label={`${stageProgress(task)}% completo`}>
              <span style={{ width: `${stageProgress(task)}%` }} />
            </span>
          </button>
        ))}
        {teamTasks.length === 0 && <div className="empty-state">Nenhuma demanda registrada para este time.</div>}
      </div>
    </section>
  );
}

function Stat({ label, value, tone = 'neutral' }: { label: string; value: number | string; tone?: 'neutral' | 'good' | 'bad' }) {
  return (
    <div className={`mini-stat mini-stat--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SystemReadiness({
  connected,
  health,
}: {
  connected: boolean;
  health: SystemHealth | null;
}) {
  const items = [
    { label: 'API', value: health?.api ?? 'loading', tone: healthTone(health?.api) },
    { label: 'WebSocket', value: connected ? 'online' : 'offline', tone: connected ? 'good' : 'bad' },
    { label: 'Redis', value: health?.redis ?? 'loading', tone: healthTone(health?.redis, health?.event_bus_persistent) },
    { label: 'Ollama', value: health?.ollama ?? 'loading', tone: healthTone(health?.ollama) },
  ];

  return (
    <section className="readiness-panel">
      <div className="section-head">
        <div>
          <p className="eyebrow">System readiness</p>
          <h2>Production posture</h2>
        </div>
        <span className={`health-pill health-pill--${health?.event_bus_persistent ? 'good' : 'warn'}`}>
          {health?.event_bus_persistent ? 'persistent events' : 'events degraded'}
        </span>
      </div>
      <div className="readiness-grid">
        {items.map((item) => (
          <div className={`readiness-item readiness-item--${item.tone}`} key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
      <p className="readiness-panel__note">
        {health?.event_bus_persistent
          ? `${health.available_models.length} modelos locais disponíveis e EventBus persistente.`
          : 'Redis real ainda não está ativo; o sistema roda, mas histórico de eventos não sobrevive a restart.'}
      </p>
    </section>
  );
}

function AgentCapacity({
  agents,
  onSelectAgent,
}: {
  agents: Agent[];
  onSelectAgent: (agentId: string | null) => void;
}) {
  const grouped = useMemo(() => {
    const byTeam: Record<string, Agent[]> = { dev: [], marketing: [], orchestrator: [] };
    for (const agent of agents) {
      byTeam[agent.team]?.push(agent);
    }
    return byTeam;
  }, [agents]);

  return (
    <section className="capacity-panel">
      <div className="section-head">
        <div>
          <p className="eyebrow">Agent capacity</p>
          <h2>Responsabilidade por time</h2>
        </div>
        <span className="section-badge">{agents.length} agentes</span>
      </div>
      <div className="capacity-teams">
        {Object.entries(grouped).map(([team, teamAgents]) => (
          <div className="capacity-team" key={team}>
            <span className="capacity-team__name">{team}</span>
            <div className="capacity-team__agents">
              {teamAgents.map((agent) => (
                <button className="agent-row" key={agent.agent_id} onClick={() => onSelectAgent(agent.agent_id)}>
                  <span className="agent-row__dot" style={{ background: agent.color, boxShadow: `0 0 18px ${agent.color}` }} />
                  <span>
                    <strong>{agent.agent_name}</strong>
                    <small>{roleLabel(agent.agent_role)} · {agent.status}</small>
                  </span>
                  <em>{agent.completed_tasks}</em>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function TaskInspector({
  task,
  logs,
  logsLoading,
}: {
  task: OfficeTask | null;
  logs: ExecutionLogItem[];
  logsLoading: boolean;
}) {
  if (!task) {
    return (
      <section className="task-inspector-pro">
        <div className="empty-state">Selecione uma demanda para inspecionar pipeline, gargalos e logs.</div>
      </section>
    );
  }

  const recentLogs = logs.slice(-7).reverse();
  const hasCommitEvidence = logs.some((log) =>
    `${log.stage} ${log.message}`.toLowerCase().includes('commit'),
  );

  return (
    <section className="task-inspector-pro">
      <div className="section-head">
        <div>
          <p className="eyebrow">Task inspector</p>
          <h2>{task.title}</h2>
        </div>
        <span className={`health-pill health-pill--${statusTone(task)}`}>{task.status}</span>
      </div>

      <div className="inspector-meta">
        <span>Team: <strong>{task.team}</strong></span>
        <span>Owner: <strong>{task.currentAgentRole ?? 'CROWN'}</strong></span>
        <span>Due: <strong>{formatDateLabel(task.desiredDueDate)}</strong></span>
        <span>Commit evidence: <strong>{hasCommitEvidence ? 'detected' : 'pending'}</strong></span>
      </div>

      <div className="stage-rail">
        {task.stages.map((stage) => (
          <div className={`stage-rail__step stage-rail__step--${stage.state}`} key={stage.id}>
            <span>{stage.label}</span>
            <strong>{stage.owner}</strong>
            <small>{stage.detail}</small>
          </div>
        ))}
      </div>

      {task.bottlenecks.length > 0 && (
        <div className="risk-list">
          {task.bottlenecks.map((bottleneck) => (
            <div key={bottleneck}>{bottleneck}</div>
          ))}
        </div>
      )}

      <div className="trace-log">
        <div className="trace-log__head">
          <span>Execution trace</span>
          <small>{logsLoading ? 'loading' : `${recentLogs.length} recentes`}</small>
        </div>
        {logsLoading ? (
          <div className="empty-state">Carregando logs...</div>
        ) : recentLogs.length > 0 ? (
          recentLogs.map((log) => (
            <div className="trace-log__row" key={`${log.timestamp}-${log.stage}-${log.message}`}>
              <code>{log.stage}</code>
              <span>{log.message}</span>
            </div>
          ))
        ) : (
          <div className="empty-state">Nenhum log detalhado para esta demanda.</div>
        )}
      </div>
    </section>
  );
}

function PortfolioQueue({
  tasks,
  loading,
  selectedTask,
  onSelectTask,
}: {
  tasks: OfficeTask[];
  loading: boolean;
  selectedTask: OfficeTask | null;
  onSelectTask: (requestId: string) => void;
}) {
  return (
    <section className="portfolio-queue">
      <div className="section-head">
        <div>
          <p className="eyebrow">Portfolio queue</p>
          <h2>Prioridade e SLA</h2>
        </div>
        <span className="section-badge">{tasks.length} demandas</span>
      </div>
      <div className="portfolio-queue__list">
        {loading ? (
          <div className="empty-state">Carregando fila operacional...</div>
        ) : (
          tasks.map((task) => (
            <TaskNode
              key={task.requestId}
              task={task}
              selected={selectedTask?.requestId === task.requestId}
              onClick={onSelectTask}
            />
          ))
        )}
      </div>
    </section>
  );
}

export function CommandCenter({
  connected,
  agents,
  tasks,
  loading,
  error,
  selectedTask,
  selectedLogs,
  logsLoading,
  health,
  selectedAgentId,
  onSelectTask,
  onSelectAgent,
  ActivityFeed,
}: CommandCenterProps) {
  const metrics = useMemo(() => buildMetrics(tasks, agents, health), [tasks, agents, health]);
  const urgentTask = tasks.find((task) => task.slaState === 'breached' || task.bottlenecks.length > 0) ?? tasks.find(taskIsOpen);

  return (
    <main className="command-center">
      <section className="command-hero">
        <div>
          <p className="eyebrow">IRIS Command Center</p>
          <h1>Gestão operacional de agentes para Dev e Marketing.</h1>
          <p>
            Uma superfície de decisão para fila, SLA, squads, evidência de entrega,
            integridade técnica e capacidade dos times.
          </p>
        </div>
        <div className="command-hero__decision">
          <span>Decisão agora</span>
          <strong>{urgentTask ? urgentTask.title : 'Nenhuma demanda crítica aberta'}</strong>
          <small>{urgentTask ? `${urgentTask.team.toUpperCase()} · ${urgentTask.stageLabel}` : 'Sistema sem bloqueio operacional'}</small>
        </div>
      </section>

      <section className="metric-strip">
        {metrics.map((metric) => (
          <div className={getToneClass(metric.tone)} key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </div>
        ))}
      </section>

      <div className="command-layout">
        <div className="command-layout__main">
          <div className="workstream-grid">
            <TeamWorkstream team="dev" tasks={tasks} agents={agents} onSelectTask={onSelectTask} />
            <TeamWorkstream team="marketing" tasks={tasks} agents={agents} onSelectTask={onSelectTask} />
          </div>

          <TaskInspector task={selectedTask} logs={selectedLogs} logsLoading={logsLoading} />
        </div>

        <aside className="command-layout__side">
          <SystemReadiness connected={connected} health={health} />
          <PortfolioQueue tasks={tasks} loading={loading} selectedTask={selectedTask} onSelectTask={onSelectTask} />
          <AgentCapacity agents={agents} onSelectAgent={onSelectAgent} />
          <section className="activity-panel-pro">
            <div className="section-head">
              <div>
                <p className="eyebrow">Realtime trace</p>
                <h2>Event stream</h2>
              </div>
            </div>
            <Suspense fallback={<div className="empty-state">Carregando stream...</div>}>
              <ActivityFeed />
            </Suspense>
          </section>
        </aside>
      </div>

      {error && <div className="command-error">{error}</div>}

      <AgentDetailsModal
        agentId={selectedAgentId}
        tasks={tasks}
        onClose={() => onSelectAgent(null)}
      />
    </main>
  );
}
