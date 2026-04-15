import { useEffect, useMemo, useState } from 'react';
import { getAgentProfile } from '../../data/agentProfiles';
import type { Agent } from '../../state/officeStore';
import type { AgentPersonalityConfig, ExecutionLogItem, OfficeTask } from '../../types/operations';
import { formatMinutes } from '../../utils/operations';

interface AgentOperationsProps {
  apiUrl: string;
  agents: Agent[];
  tasks: OfficeTask[];
  selectedTask: OfficeTask | null;
  selectedLogs: ExecutionLogItem[];
  logsLoading: boolean;
  selectedAgentId: string | null;
  onSelectAgent: (agentId: string | null) => void;
  onSelectTask: (requestId: string) => void;
}

interface EditableConfig {
  persona_name: string;
  mission: string;
  personality: string;
  operating_rules: string;
  autonomy_level: string;
  model_policy: string;
  visibility_level: string;
}

const DEFAULT_EDITABLE_CONFIG: EditableConfig = {
  persona_name: '',
  mission: '',
  personality: '',
  operating_rules: '',
  autonomy_level: 'supervised',
  model_policy: 'role_default',
  visibility_level: 'full_trace',
};

const isOpenTask = (task: OfficeTask) => task.status !== 'completed';

function roleLabel(role: string): string {
  return role.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getAgentTask(agent: Agent, tasks: OfficeTask[], selectedTask: OfficeTask | null): OfficeTask | null {
  const directTask = tasks.find((task) => task.taskId === agent.current_task_id);
  if (directTask) return directTask;

  const roleTask = tasks.find((task) => (
    isOpenTask(task)
    && task.team === agent.team
    && task.currentAgentRole?.toLowerCase() === agent.agent_role.toLowerCase()
  ));
  if (roleTask) return roleTask;

  if (selectedTask?.team === agent.team && selectedTask.involvedRoles.includes(agent.agent_role)) {
    return selectedTask;
  }

  return null;
}

function extractAgentLogs(agent: Agent, logs: ExecutionLogItem[]): ExecutionLogItem[] {
  return logs
    .filter((log) => (
      log.agent_id === agent.agent_id
      || log.agent_role?.toLowerCase() === agent.agent_role.toLowerCase()
      || String(log.metadata?.assigned_role ?? '').toLowerCase() === agent.agent_role.toLowerCase()
    ))
    .slice(-12)
    .reverse();
}

function extractArtifact(logs: ExecutionLogItem[], task: OfficeTask | null): { title: string; body: string; files: string[] } {
  const files = new Set<string>();
  const fragments: string[] = [];

  for (const log of logs) {
    const metadata = log.metadata ?? {};
    const outputPreview = metadata.output_preview;
    const changedFiles = metadata.files_changed ?? metadata.files ?? metadata.file_paths;

    if (typeof outputPreview === 'string' && outputPreview.trim()) {
      fragments.push(outputPreview.trim());
    }

    if (Array.isArray(changedFiles)) {
      for (const file of changedFiles) {
        if (typeof file === 'string' && file.trim()) files.add(file.trim());
      }
    }

    if (typeof metadata.file === 'string') files.add(metadata.file);
  }

  if (task?.lastExecutionMessage) {
    fragments.push(task.lastExecutionMessage);
  }

  const body = fragments.length > 0
    ? fragments.slice(0, 5).join('\n\n')
    : 'Nenhum artefato de código foi publicado ainda. Quando o agente executar tool calls, commits ou patches, este painel deve mostrar diff, arquivos e saída validável.';

  return {
    title: files.size > 0 ? 'Live artifact / changed files' : 'Live artifact',
    body,
    files: Array.from(files),
  };
}

function toEditableConfig(config: AgentPersonalityConfig | null, agent: Agent | null): EditableConfig {
  if (!agent) return DEFAULT_EDITABLE_CONFIG;
  const profile = getAgentProfile(agent.agent_id, agent.agent_role);

  return {
    persona_name: config?.persona_name ?? profile.codename,
    mission: config?.mission ?? profile.mission,
    personality: (config?.personality ?? profile.personality).join('\n'),
    operating_rules: (config?.operating_rules ?? [
      profile.signature,
      'Registrar decisoes, tool calls, arquivos e evidencias antes de concluir.',
      'Escalar bloqueios ao orquestrador em vez de simular sucesso.',
    ]).join('\n'),
    autonomy_level: config?.autonomy_level ?? 'supervised',
    model_policy: config?.model_policy ?? 'role_default',
    visibility_level: config?.visibility_level ?? 'full_trace',
  };
}

function parseLines(value: string): string[] {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

function AgentRoster({
  agents,
  selectedAgent,
  tasks,
  onSelectAgent,
}: {
  agents: Agent[];
  selectedAgent: Agent | null;
  tasks: OfficeTask[];
  onSelectAgent: (agentId: string | null) => void;
}) {
  const grouped = useMemo(() => {
    const groups: Record<string, Agent[]> = { orchestrator: [], dev: [], marketing: [] };
    for (const agent of agents) {
      groups[agent.team]?.push(agent);
    }
    return groups;
  }, [agents]);

  return (
    <aside className="agent-ops-roster">
      <div className="section-head">
        <div>
          <p className="eyebrow">Agent directory</p>
          <h2>Times operacionais</h2>
        </div>
        <span className="section-badge">{agents.length} agentes</span>
      </div>

      <div className="agent-ops-roster__groups">
        {Object.entries(grouped).map(([team, teamAgents]) => (
          <div className="agent-ops-group" key={team}>
            <span className="agent-ops-group__label">{team}</span>
            {teamAgents.map((agent) => {
              const task = getAgentTask(agent, tasks, null);
              return (
                <button
                  className={selectedAgent?.agent_id === agent.agent_id ? 'agent-ops-row agent-ops-row--active' : 'agent-ops-row'}
                  key={agent.agent_id}
                  onClick={() => onSelectAgent(agent.agent_id)}
                >
                  <span className="agent-ops-row__signal" style={{ background: agent.color }} />
                  <span>
                    <strong>{agent.agent_name}</strong>
                    <small>{roleLabel(agent.agent_role)} · {agent.status}</small>
                  </span>
                  <em>{task ? 'busy' : 'ready'}</em>
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </aside>
  );
}

function AgentWorkbench({
  agent,
  task,
  logs,
  logsLoading,
  onSelectTask,
}: {
  agent: Agent | null;
  task: OfficeTask | null;
  logs: ExecutionLogItem[];
  logsLoading: boolean;
  onSelectTask: (requestId: string) => void;
}) {
  if (!agent) {
    return (
      <section className="agent-workbench">
        <div className="empty-state">Selecione um agente para ver execução, artefatos, logs e dependências.</div>
      </section>
    );
  }

  const profile = getAgentProfile(agent.agent_id, agent.agent_role);
  const artifact = extractArtifact(logs, task);

  return (
    <section className="agent-workbench">
      <div className="agent-workbench__hero">
        <div>
          <p className="eyebrow">{agent.team} / {agent.agent_role}</p>
          <h1>{profile.codename}</h1>
          <p>{profile.summary}</p>
        </div>
        <div className="agent-workbench__status">
          <span style={{ background: agent.color }} />
          <strong>{agent.status}</strong>
          <small>{agent.completed_tasks} entregas · {agent.error_count} falhas</small>
        </div>
      </div>

      <div className="agent-workbench__grid">
        <div className="agent-run-card">
          <div className="section-head">
            <div>
              <p className="eyebrow">Current execution</p>
              <h2>{task ? task.title : 'Sem execução ativa'}</h2>
            </div>
            {task && <button className="text-action" onClick={() => onSelectTask(task.requestId)}>abrir task</button>}
          </div>

          {task ? (
            <>
              <div className="agent-run-card__meta">
                <span>Prioridade <strong>P{task.priority}</strong></span>
                <span>SLA <strong>{task.slaState}</strong></span>
                <span>Fila <strong>{formatMinutes(task.queueMinutes)}</strong></span>
              </div>
              <div className="agent-stage-stack">
                {task.stages.map((stage) => (
                  <div className={`agent-stage agent-stage--${stage.state}`} key={stage.id}>
                    <span>{stage.label}</span>
                    <strong>{stage.owner}</strong>
                    <small>{stage.detail}</small>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="empty-state">Agente pronto. Sem task vinculada neste momento.</div>
          )}
        </div>

        <div className="agent-artifact-panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">Build visibility</p>
              <h2>{artifact.title}</h2>
            </div>
            <span className="section-badge">{artifact.files.length} files</span>
          </div>
          {artifact.files.length > 0 && (
            <div className="artifact-file-list">
              {artifact.files.map((file) => <code key={file}>{file}</code>)}
            </div>
          )}
          <pre className="artifact-code"><code>{artifact.body}</code></pre>
        </div>
      </div>

      <div className="agent-trace-panel">
        <div className="section-head">
          <div>
            <p className="eyebrow">Agent trace</p>
            <h2>Ações confirmadas</h2>
          </div>
          <span className="section-badge">{logsLoading ? 'loading' : `${logs.length} eventos`}</span>
        </div>
        <div className="agent-trace-list">
          {logsLoading ? (
            <div className="empty-state">Carregando execução...</div>
          ) : logs.length > 0 ? (
            logs.map((log) => (
              <div className="agent-trace-row" key={`${log.timestamp}-${log.stage}-${log.message}`}>
                <code>{log.stage}</code>
                <span>{log.message}</span>
                <small>{new Date(log.timestamp).toLocaleTimeString()}</small>
              </div>
            ))
          ) : (
            <div className="empty-state">Sem logs específicos deste agente na task selecionada.</div>
          )}
        </div>
      </div>
    </section>
  );
}

function AgentConfigEditor({
  apiUrl,
  agent,
}: {
  apiUrl: string;
  agent: Agent | null;
}) {
  const [config, setConfig] = useState<AgentPersonalityConfig | null>(null);
  const [form, setForm] = useState<EditableConfig>(DEFAULT_EDITABLE_CONFIG);
  const [status, setStatus] = useState<'idle' | 'loading' | 'saving' | 'saved' | 'error'>('idle');

  useEffect(() => {
    let cancelled = false;

    async function loadConfig() {
      if (!agent) {
        setConfig(null);
        setForm(DEFAULT_EDITABLE_CONFIG);
        return;
      }

      setStatus('loading');
      try {
        const response = await fetch(`${apiUrl}/agents/${agent.agent_id}/config`);
        if (!response.ok) {
          throw new Error(`Config indisponivel (${response.status})`);
        }
        const data = (await response.json()) as AgentPersonalityConfig;
        if (!cancelled) {
          setConfig(data);
          setForm(toEditableConfig(data, agent));
          setStatus('idle');
        }
      } catch {
        if (!cancelled) {
          setConfig(null);
          setForm(toEditableConfig(null, agent));
          setStatus('error');
        }
      }
    }

    loadConfig();
    return () => {
      cancelled = true;
    };
  }, [apiUrl, agent]);

  async function saveConfig() {
    if (!agent) return;
    setStatus('saving');

    const payload = {
      persona_name: form.persona_name,
      mission: form.mission,
      personality: parseLines(form.personality),
      operating_rules: parseLines(form.operating_rules),
      autonomy_level: form.autonomy_level,
      model_policy: form.model_policy,
      visibility_level: form.visibility_level,
    };

    try {
      const response = await fetch(`${apiUrl}/agents/${agent.agent_id}/config`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(`Falha ao salvar (${response.status})`);
      }
      const data = (await response.json()) as AgentPersonalityConfig;
      setConfig(data);
      setForm(toEditableConfig(data, agent));
      setStatus('saved');
    } catch {
      setStatus('error');
    }
  }

  if (!agent) {
    return (
      <aside className="agent-config-editor">
        <div className="empty-state">Selecione um agente para editar personalidade e regras operacionais.</div>
      </aside>
    );
  }

  return (
    <aside className="agent-config-editor">
      <div className="section-head">
        <div>
          <p className="eyebrow">Personality config</p>
          <h2>Controle do agente</h2>
        </div>
        <span className={`health-pill health-pill--${status === 'error' ? 'bad' : status === 'saved' ? 'good' : 'neutral'}`}>
          {status}
        </span>
      </div>

      <label className="config-field">
        <span>Nome operacional</span>
        <input
          value={form.persona_name}
          onChange={(event) => setForm({ ...form, persona_name: event.target.value })}
        />
      </label>

      <label className="config-field">
        <span>Missão</span>
        <textarea
          rows={4}
          value={form.mission}
          onChange={(event) => setForm({ ...form, mission: event.target.value })}
        />
      </label>

      <label className="config-field">
        <span>Traços de personalidade</span>
        <textarea
          rows={5}
          value={form.personality}
          onChange={(event) => setForm({ ...form, personality: event.target.value })}
        />
      </label>

      <label className="config-field">
        <span>Regras operacionais</span>
        <textarea
          rows={6}
          value={form.operating_rules}
          onChange={(event) => setForm({ ...form, operating_rules: event.target.value })}
        />
      </label>

      <div className="config-split">
        <label className="config-field">
          <span>Autonomia</span>
          <select
            value={form.autonomy_level}
            onChange={(event) => setForm({ ...form, autonomy_level: event.target.value })}
          >
            <option value="supervised">Supervised</option>
            <option value="guided">Guided</option>
            <option value="autonomous">Autonomous</option>
          </select>
        </label>

        <label className="config-field">
          <span>Modelo</span>
          <select
            value={form.model_policy}
            onChange={(event) => setForm({ ...form, model_policy: event.target.value })}
          >
            <option value="role_default">Role default</option>
            <option value="fast">Fast</option>
            <option value="code">Code</option>
            <option value="vision">Vision</option>
          </select>
        </label>
      </div>

      <label className="config-field">
        <span>Visibilidade</span>
        <select
          value={form.visibility_level}
          onChange={(event) => setForm({ ...form, visibility_level: event.target.value })}
        >
          <option value="full_trace">Full trace</option>
          <option value="summary_only">Summary only</option>
          <option value="restricted">Restricted</option>
        </select>
      </label>

      <button className="primary-action" onClick={saveConfig} disabled={status === 'saving' || status === 'loading'}>
        Salvar configuração
      </button>

      {config?.updated_at && (
        <p className="config-footnote">Última atualização: {new Date(config.updated_at).toLocaleString()}</p>
      )}
    </aside>
  );
}

export function AgentOperations({
  apiUrl,
  agents,
  tasks,
  selectedTask,
  selectedLogs,
  logsLoading,
  selectedAgentId,
  onSelectAgent,
  onSelectTask,
}: AgentOperationsProps) {
  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.agent_id === selectedAgentId) ?? agents[0] ?? null,
    [agents, selectedAgentId],
  );
  const selectedAgentTask = selectedAgent ? getAgentTask(selectedAgent, tasks, selectedTask) : null;
  const agentLogs = selectedAgent ? extractAgentLogs(selectedAgent, selectedLogs) : [];

  useEffect(() => {
    if (!selectedAgentId && selectedAgent) {
      onSelectAgent(selectedAgent.agent_id);
    }
  }, [onSelectAgent, selectedAgent, selectedAgentId]);

  return (
    <main className="agent-ops-shell">
      <section className="agent-ops-header">
        <div>
          <p className="eyebrow">Agent Operations</p>
          <h1>Controle profissional de agentes, execução e personalidade.</h1>
          <p>
            Substitui o mapa lúdico por uma mesa operacional: clique no agente, veja configuração,
            execução ativa, trace, dependências, arquivos e evidências.
          </p>
        </div>
        <div className="agent-ops-principles">
          <span>Trace first</span>
          <span>Configurable persona</span>
          <span>Artifact evidence</span>
        </div>
      </section>

      <div className="agent-ops-layout">
        <AgentRoster
          agents={agents}
          selectedAgent={selectedAgent}
          tasks={tasks}
          onSelectAgent={onSelectAgent}
        />
        <AgentWorkbench
          agent={selectedAgent}
          task={selectedAgentTask}
          logs={agentLogs}
          logsLoading={logsLoading}
          onSelectTask={onSelectTask}
        />
        <AgentConfigEditor apiUrl={apiUrl} agent={selectedAgent} />
      </div>
    </main>
  );
}
