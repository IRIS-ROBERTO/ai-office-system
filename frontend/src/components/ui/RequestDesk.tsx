import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useOfficeStore } from '../../state/officeStore';

type ServiceRequest = {
  request_id: string;
  title: string;
  team: string;
  status: string;
  stage_label: string;
  requester_name?: string | null;
  requester_team?: string | null;
  urgency: string;
  priority: number;
  desired_due_date?: string | null;
  acceptance_criteria?: string | null;
  request: string;
  task_id?: string | null;
  current_agent_role?: string | null;
  tested_by_team: boolean;
  approved_by_orchestrator: boolean;
  last_execution_message?: string | null;
  last_execution_stage?: string | null;
  execution_log_size: number;
  created_at: string;
  updated_at: string;
};

type ServiceRequestListResponse = {
  items: ServiceRequest[];
  total: number;
};

type RequestDeskProps = {
  apiUrl: string;
};

const CARD_BG = 'rgba(255,255,255,0.03)';
const BORDER = 'rgba(255,255,255,0.08)';

const initialForm = {
  title: '',
  team: 'dev',
  requester_name: '',
  requester_team: '',
  urgency: 'medium',
  desired_due_date: '',
  request: '',
  acceptance_criteria: '',
};

function statusAccent(status: string) {
  switch (status) {
    case 'completed':
      return '#22c55e';
    case 'awaiting_approval':
      return '#fbbf24';
    case 'in_testing':
      return '#06b6d4';
    case 'planned':
      return '#818cf8';
    case 'changes_requested':
      return '#ef4444';
    case 'triage':
      return '#f59e0b';
    default:
      return '#94a3b8';
  }
}

function urgencyAccent(urgency: string) {
  switch (urgency) {
    case 'critical':
      return '#ef4444';
    case 'high':
      return '#f97316';
    case 'medium':
      return '#fbbf24';
    default:
      return '#94a3b8';
  }
}

function formatDate(value?: string | null) {
  if (!value) return 'Sem prazo';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const RequestDesk: React.FC<RequestDeskProps> = ({ apiUrl }) => {
  const orchestrator = useOfficeStore((state) =>
    Object.values(state.agents).find((agent) => agent.team === 'orchestrator')
  );
  const [items, setItems] = useState<ServiceRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState(initialForm);

  const loadRequests = useCallback(async () => {
    try {
      const response = await fetch(`${apiUrl}/service-requests`);
      if (!response.ok) {
        throw new Error(`Falha ao carregar backlog (${response.status})`);
      }

      const data = await response.json() as ServiceRequestListResponse;
      setItems(data.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao carregar backlog');
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    loadRequests();
    const id = window.setInterval(loadRequests, 5000);
    return () => window.clearInterval(id);
  }, [loadRequests]);

  const stats = useMemo(() => {
    return {
      total: items.length,
      running: items.filter((item) => ['triage', 'planned', 'in_execution', 'in_testing'].includes(item.status)).length,
      approval: items.filter((item) => item.status === 'awaiting_approval').length,
      done: items.filter((item) => item.status === 'completed').length,
    };
  }, [items]);

  const handleChange = useCallback((field: keyof typeof initialForm, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  }, []);

  const handleSubmit = useCallback(async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);

    try {
      const response = await fetch(`${apiUrl}/service-requests`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...form,
          requester_name: form.requester_name || null,
          requester_team: form.requester_team || null,
          desired_due_date: form.desired_due_date || null,
          acceptance_criteria: form.acceptance_criteria || null,
        }),
      });

      if (!response.ok) {
        throw new Error(`Falha ao criar solicitacao (${response.status})`);
      }

      setForm(initialForm);
      await loadRequests();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao criar solicitacao');
    } finally {
      setSubmitting(false);
    }
  }, [apiUrl, form, loadRequests]);

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'minmax(340px, 420px) minmax(0, 1fr)',
      gap: 18,
      padding: 18,
      height: '100%',
      overflow: 'hidden',
      background: 'radial-gradient(circle at top left, rgba(251,191,36,0.08), transparent 32%), #03030a',
    }}>
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        minHeight: 0,
      }}>
        <div style={{
          padding: 18,
          borderRadius: 18,
          border: `1px solid ${BORDER}`,
          background: 'linear-gradient(180deg, rgba(12,12,22,0.94), rgba(8,8,18,0.92))',
          boxShadow: '0 20px 50px rgba(0,0,0,0.35)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <div style={{ fontSize: 11, color: '#fbbf24', letterSpacing: 2, textTransform: 'uppercase' }}>
                Portal de Solicitações
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#f8fafc', marginTop: 6 }}>
                Entrada unica do backlog
              </div>
            </div>
            <div style={{
              padding: '10px 12px',
              borderRadius: 14,
              border: '1px solid rgba(251,191,36,0.32)',
              background: 'rgba(251,191,36,0.08)',
              minWidth: 130,
            }}>
              <div style={{ fontSize: 10, color: '#fbbf24', letterSpacing: 1.4, textTransform: 'uppercase' }}>
                ♛ Orchestrator
              </div>
              <div style={{ marginTop: 6, fontSize: 14, fontWeight: 700, color: '#f8fafc' }}>
                {orchestrator?.agent_name ?? 'Offline'}
              </div>
              <div style={{ marginTop: 4, fontSize: 11, color: orchestrator ? '#fbbf24' : '#94a3b8' }}>
                {orchestrator ? orchestrator.status : 'sem presenca visual'}
              </div>
            </div>
          </div>
          <div style={{ marginTop: 14, fontSize: 13, lineHeight: 1.6, color: '#cbd5e1' }}>
            Toda solicitacao entra por aqui, passa por backlog, execucao do time, testes e aprovacao final do orquestrador.
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          padding: 18,
          borderRadius: 18,
          border: `1px solid ${BORDER}`,
          background: 'linear-gradient(180deg, rgba(9,11,20,0.96), rgba(5,7,14,0.92))',
          overflow: 'auto',
        }}>
          <div style={{ fontSize: 11, color: '#94a3b8', letterSpacing: 2, textTransform: 'uppercase' }}>
            Nova Solicitação
          </div>

          <input
            value={form.title}
            onChange={(event) => handleChange('title', event.target.value)}
            placeholder="Titulo da demanda"
            required
            style={inputStyle}
          />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <select value={form.team} onChange={(event) => handleChange('team', event.target.value)} style={inputStyle}>
              <option value="dev">Time Dev</option>
              <option value="marketing">Time Marketing</option>
            </select>
            <select value={form.urgency} onChange={(event) => handleChange('urgency', event.target.value)} style={inputStyle}>
              <option value="low">Baixa</option>
              <option value="medium">Media</option>
              <option value="high">Alta</option>
              <option value="critical">Critica</option>
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <input
              value={form.requester_name}
              onChange={(event) => handleChange('requester_name', event.target.value)}
              placeholder="Nome do solicitante"
              style={inputStyle}
            />
            <input
              value={form.requester_team}
              onChange={(event) => handleChange('requester_team', event.target.value)}
              placeholder="Area ou time solicitante"
              style={inputStyle}
            />
          </div>

          <input
            value={form.desired_due_date}
            onChange={(event) => handleChange('desired_due_date', event.target.value)}
            placeholder="Prazo desejado"
            style={inputStyle}
          />

          <textarea
            value={form.request}
            onChange={(event) => handleChange('request', event.target.value)}
            placeholder="Descreva a demanda com contexto suficiente para o time executar"
            required
            rows={7}
            style={{ ...inputStyle, resize: 'vertical', minHeight: 150 }}
          />

          <textarea
            value={form.acceptance_criteria}
            onChange={(event) => handleChange('acceptance_criteria', event.target.value)}
            placeholder="Resultado esperado e criterio de aceite"
            rows={4}
            style={{ ...inputStyle, resize: 'vertical', minHeight: 96 }}
          />

          <button
            type="submit"
            disabled={submitting}
            style={{
              border: 'none',
              borderRadius: 14,
              padding: '14px 16px',
              background: submitting ? 'rgba(251,191,36,0.4)' : 'linear-gradient(135deg, #fbbf24, #f59e0b)',
              color: '#111827',
              fontWeight: 800,
              letterSpacing: 0.6,
              cursor: submitting ? 'wait' : 'pointer',
            }}
          >
            {submitting ? 'Enviando...' : 'Enviar para backlog'}
          </button>

          {error ? (
            <div style={{ fontSize: 12, color: '#fca5a5', lineHeight: 1.5 }}>
              {error}
            </div>
          ) : null}
        </form>
      </div>

      <div style={{
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
          gap: 12,
        }}>
          <StatCard label="Total" value={stats.total} color="#e2e8f0" />
          <StatCard label="Rodando" value={stats.running} color="#f59e0b" />
          <StatCard label="Aprovacao" value={stats.approval} color="#fbbf24" />
          <StatCard label="Concluidas" value={stats.done} color="#22c55e" />
        </div>

        <div style={{
          flex: 1,
          minHeight: 0,
          borderRadius: 18,
          border: `1px solid ${BORDER}`,
          background: 'linear-gradient(180deg, rgba(8,10,18,0.96), rgba(5,7,14,0.94))',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '16px 18px',
            borderBottom: `1px solid ${BORDER}`,
          }}>
            <div>
              <div style={{ fontSize: 11, color: '#94a3b8', letterSpacing: 2, textTransform: 'uppercase' }}>
                Backlog
              </div>
              <div style={{ marginTop: 5, fontSize: 18, fontWeight: 800, color: '#f8fafc' }}>
                Solicitações em andamento
              </div>
            </div>
            <button
              onClick={loadRequests}
              style={{
                borderRadius: 12,
                border: `1px solid ${BORDER}`,
                background: CARD_BG,
                color: '#cbd5e1',
                padding: '10px 12px',
                cursor: 'pointer',
              }}
            >
              Atualizar
            </button>
          </div>

          <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
            {loading ? (
              <div style={emptyStyle}>Carregando backlog...</div>
            ) : items.length === 0 ? (
              <div style={emptyStyle}>Nenhuma solicitacao registrada ainda.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {items.map((item) => (
                  <div
                    key={item.request_id}
                    style={{
                      borderRadius: 16,
                      border: `1px solid ${BORDER}`,
                      background: CARD_BG,
                      padding: 16,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                          <div style={{ fontSize: 17, fontWeight: 800, color: '#f8fafc' }}>
                            {item.title}
                          </div>
                          <Badge color={statusAccent(item.status)}>{item.stage_label}</Badge>
                          <Badge color={urgencyAccent(item.urgency)}>{item.urgency}</Badge>
                        </div>
                        <div style={{ marginTop: 8, fontSize: 12, color: '#94a3b8', lineHeight: 1.5 }}>
                          {item.requester_team || 'Area nao informada'} · {item.team.toUpperCase()} · Atualizado em {formatDate(item.updated_at)}
                        </div>
                      </div>
                      <div style={{
                        minWidth: 180,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 8,
                        alignItems: 'flex-end',
                      }}>
                        <Flag ok={item.tested_by_team} label="Testado pelo time" />
                        <Flag ok={item.approved_by_orchestrator} label="Aprovado pelo orquestrador" />
                      </div>
                    </div>

                    <div style={{ marginTop: 12, fontSize: 13, lineHeight: 1.7, color: '#dbe4f0' }}>
                      {item.request}
                    </div>

                    <div style={{
                      marginTop: 12,
                      borderRadius: 12,
                      border: `1px solid ${BORDER}`,
                      background: 'rgba(255,255,255,0.025)',
                      padding: '10px 12px',
                    }}>
                      <div style={{ fontSize: 10, color: '#64748b', letterSpacing: 1.2, textTransform: 'uppercase' }}>
                        Ultima execucao
                      </div>
                      <div style={{ marginTop: 6, fontSize: 12, color: '#e2e8f0', lineHeight: 1.55 }}>
                        {item.last_execution_message || 'Sem trilha de execucao ainda.'}
                      </div>
                      <div style={{ marginTop: 6, fontSize: 11, color: '#94a3b8' }}>
                        {item.last_execution_stage || 'sem etapa'} · {item.execution_log_size} registros
                      </div>
                    </div>

                    <div style={{
                      marginTop: 14,
                      display: 'grid',
                      gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                      gap: 10,
                    }}>
                      <InfoBlock label="Solicitante" value={item.requester_name || 'Nao informado'} />
                      <InfoBlock label="Papel atual" value={item.current_agent_role || 'orchestrator'} />
                      <InfoBlock label="Prazo" value={item.desired_due_date || 'Sem prazo'} />
                      <InfoBlock label="Task" value={item.task_id?.slice(0, 12) || 'Sem task'} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  borderRadius: 12,
  border: '1px solid rgba(255,255,255,0.08)',
  background: 'rgba(255,255,255,0.04)',
  color: '#f8fafc',
  padding: '12px 14px',
  outline: 'none',
  fontSize: 13,
  lineHeight: 1.5,
};

const emptyStyle: React.CSSProperties = {
  height: '100%',
  minHeight: 240,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: '#64748b',
  fontSize: 13,
  textAlign: 'center',
};

const StatCard: React.FC<{ label: string; value: number; color: string }> = ({ label, value, color }) => (
  <div style={{
    borderRadius: 16,
    border: `1px solid ${BORDER}`,
    background: CARD_BG,
    padding: '16px 18px',
  }}>
    <div style={{ fontSize: 11, color: '#94a3b8', letterSpacing: 1.5, textTransform: 'uppercase' }}>
      {label}
    </div>
    <div style={{ marginTop: 8, fontSize: 28, fontWeight: 800, color }}>
      {value}
    </div>
  </div>
);

const Badge: React.FC<{ color: string; children: React.ReactNode }> = ({ color, children }) => (
  <span style={{
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    borderRadius: 999,
    border: `1px solid ${color}55`,
    background: `${color}14`,
    color,
    padding: '5px 10px',
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  }}>
    {children}
  </span>
);

const Flag: React.FC<{ ok: boolean; label: string }> = ({ ok, label }) => (
  <div style={{
    width: '100%',
    borderRadius: 12,
    border: `1px solid ${ok ? 'rgba(34,197,94,0.3)' : 'rgba(148,163,184,0.22)'}`,
    background: ok ? 'rgba(34,197,94,0.1)' : 'rgba(148,163,184,0.08)',
    color: ok ? '#22c55e' : '#94a3b8',
    padding: '9px 11px',
    fontSize: 11,
    fontWeight: 700,
    textAlign: 'center',
  }}>
    {ok ? 'OK' : 'Pendente'} · {label}
  </div>
);

const InfoBlock: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div style={{
    borderRadius: 12,
    border: `1px solid ${BORDER}`,
    background: 'rgba(255,255,255,0.02)',
    padding: '10px 12px',
  }}>
    <div style={{ fontSize: 10, color: '#64748b', letterSpacing: 1.2, textTransform: 'uppercase' }}>
      {label}
    </div>
    <div style={{ marginTop: 6, fontSize: 12, color: '#e2e8f0', lineHeight: 1.5 }}>
      {value}
    </div>
  </div>
);

export default RequestDesk;
