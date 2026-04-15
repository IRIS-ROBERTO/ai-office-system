import { Suspense, lazy, startTransition, useEffect, useMemo, useState } from 'react';
import { AgentOperations } from './components/command/AgentOperations';
import { CommandCenter } from './components/command/CommandCenter';
import { useOperationsData } from './hooks/useOperationsData';
import { useOfficeStore, type AgentBootstrapRecord } from './state/officeStore';
import { useEventStream } from './websocket/useEventStream';

const ActivityFeed = lazy(() => import('./components/ui/ActivityFeed'));
const RequestDesk = lazy(() => import('./components/ui/RequestDesk'));

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8124';

type ActiveTab = 'command' | 'intake' | 'agents';

const panelFallback = <div className="empty-state">Carregando módulo operacional...</div>;

export default function App() {
  const { connected } = useEventStream();
  const hydrateAgents = useOfficeStore((state) => state.hydrateAgents);
  const agents = useOfficeStore((state) => state.agents);

  const [activeTab, setActiveTab] = useState<ActiveTab>('command');
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  const {
    tasks,
    loading,
    error,
    selectedLogs,
    logsLoading,
    health,
  } = useOperationsData(API_URL, selectedRequestId);

  const agentArr = useMemo(() => Object.values(agents), [agents]);
  const selectedTask = useMemo(
    () => tasks.find((task) => task.requestId === selectedRequestId) ?? tasks[0] ?? null,
    [selectedRequestId, tasks],
  );

  useEffect(() => {
    let cancelled = false;

    async function bootstrapAgents() {
      try {
        const response = await fetch(`${API_URL}/agents`);
        if (!response.ok) {
          throw new Error(`Failed to fetch agents: ${response.status}`);
        }

        const records = (await response.json()) as AgentBootstrapRecord[];
        if (!cancelled) {
          startTransition(() => hydrateAgents(records));
        }
      } catch (err) {
        console.warn('[App] Failed to bootstrap /agents', err);
      }
    }

    bootstrapAgents();
    const intervalId = window.setInterval(bootstrapAgents, 10000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [hydrateAgents]);

  useEffect(() => {
    if (!selectedRequestId && tasks.length > 0) {
      setSelectedRequestId(tasks[0].requestId);
    }
  }, [selectedRequestId, tasks]);

  function selectTab(tab: ActiveTab) {
    setActiveTab(tab);
    if (tab !== 'agents') {
      setSelectedAgentId(null);
    }
  }

  return (
    <div className="product-shell">
      <header className="product-topbar">
        <div className="product-brand">
          <div className="product-brand__mark">IR</div>
          <div>
            <span>IRIS AI Office System</span>
            <strong>Operational command center</strong>
          </div>
        </div>

        <nav className="product-nav" aria-label="Navegação principal">
          {[
            { id: 'command' as const, label: 'Command Center' },
            { id: 'intake' as const, label: 'Intake' },
            { id: 'agents' as const, label: 'Agent Ops' },
          ].map((tab) => (
            <button
              className={activeTab === tab.id ? 'product-nav__item product-nav__item--active' : 'product-nav__item'}
              key={tab.id}
              onClick={() => selectTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className={`topbar-status ${connected ? 'topbar-status--online' : 'topbar-status--offline'}`}>
          <span />
          {connected ? 'WS online' : 'WS offline'}
        </div>
      </header>

      {activeTab === 'command' && (
        <CommandCenter
          connected={connected}
          agents={agentArr}
          tasks={tasks}
          loading={loading}
          error={error}
          selectedTask={selectedTask}
          selectedLogs={selectedLogs}
          logsLoading={logsLoading}
          health={health}
          selectedAgentId={selectedAgentId}
          onSelectTask={setSelectedRequestId}
          onSelectAgent={setSelectedAgentId}
          ActivityFeed={ActivityFeed}
        />
      )}

      {activeTab === 'intake' && (
        <section className="module-frame">
          <Suspense fallback={panelFallback}>
            <RequestDesk apiUrl={API_URL} />
          </Suspense>
        </section>
      )}

      {activeTab === 'agents' && (
        <AgentOperations
          apiUrl={API_URL}
          agents={agentArr}
          tasks={tasks}
          selectedTask={selectedTask}
          selectedLogs={selectedLogs}
          logsLoading={logsLoading}
          selectedAgentId={selectedAgentId}
          onSelectAgent={setSelectedAgentId}
          onSelectTask={setSelectedRequestId}
        />
      )}
    </div>
  );
}
