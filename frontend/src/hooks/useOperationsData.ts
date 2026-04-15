import { startTransition, useEffect, useMemo, useState } from 'react';
import type {
  ExecutionLogItem,
  ExecutionLogResponse,
  OfficeTask,
  ServiceRequestListResponse,
  SystemHealth,
} from '../types/operations';
import { normalizeServiceRequest } from '../utils/operations';

interface OperationsDataState {
  tasks: OfficeTask[];
  loading: boolean;
  error: string | null;
  selectedLogs: ExecutionLogItem[];
  logsLoading: boolean;
  health: SystemHealth | null;
}

export function useOperationsData(apiUrl: string, selectedTaskId: string | null): OperationsDataState {
  const [tasks, setTasks] = useState<OfficeTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLogs, setSelectedLogs] = useState<ExecutionLogItem[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [health, setHealth] = useState<SystemHealth | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadSnapshot() {
      try {
        const [requestsResponse, healthResponse] = await Promise.all([
          fetch(`${apiUrl}/service-requests`),
          fetch(`${apiUrl}/health`),
        ]);

        if (!requestsResponse.ok) {
          throw new Error(`Falha ao carregar solicitacoes (${requestsResponse.status})`);
        }

        const data = (await requestsResponse.json()) as ServiceRequestListResponse;
        const healthData = healthResponse.ok ? ((await healthResponse.json()) as SystemHealth) : null;
        if (cancelled) return;

        startTransition(() => {
          setTasks(
            data.items
              .map(normalizeServiceRequest)
              .sort((a, b) => {
                if (a.status !== b.status) {
                  const openA = a.status === 'completed' ? 1 : 0;
                  const openB = b.status === 'completed' ? 1 : 0;
                  if (openA !== openB) return openA - openB;
                }
                if (a.priority !== b.priority) return b.priority - a.priority;
                return b.queueMinutes - a.queueMinutes;
              }),
          );
          setHealth(healthData);
        });
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Falha ao carregar solicitacoes');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadSnapshot();
    const intervalId = window.setInterval(loadSnapshot, 6000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [apiUrl]);

  useEffect(() => {
    let cancelled = false;

    const currentTaskId = tasks.find((task) => task.requestId === selectedTaskId)?.taskId ?? null;

    if (!currentTaskId) {
      setSelectedLogs([]);
      setLogsLoading(false);
      return;
    }

    async function loadExecutionLog() {
      setLogsLoading(true);
      try {
        const response = await fetch(`${apiUrl}/tasks/${currentTaskId}/execution-log`);
        if (!response.ok) {
          throw new Error(`Falha ao carregar logs (${response.status})`);
        }

        const data = (await response.json()) as ExecutionLogResponse;
        if (!cancelled) {
          setSelectedLogs(data.items);
        }
      } catch (err) {
        if (!cancelled) {
          setSelectedLogs([]);
          setError(err instanceof Error ? err.message : 'Falha ao carregar logs');
        }
      } finally {
        if (!cancelled) {
          setLogsLoading(false);
        }
      }
    }

    loadExecutionLog();
    return () => {
      cancelled = true;
    };
  }, [apiUrl, selectedTaskId, tasks]);

  return useMemo(
    () => ({
      tasks,
      loading,
      error,
      selectedLogs,
      logsLoading,
      health,
    }),
    [tasks, loading, error, selectedLogs, logsLoading, health],
  );
}
