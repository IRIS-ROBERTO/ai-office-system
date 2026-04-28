import React, { useCallback, useEffect, useRef, useState } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

type Finding = {
  id: string;
  source: string;
  name: string;
  title: string;
  description: string;
  url: string;
  language: string;
  license: string;
  score: number;
  grade: string;
  grade_label: string;
  breakdown: Record<string, number>;
  iris_fit: string[];
  topics: string[];
  tags: string[];
  stars: number;
  forks: number;
  downloads: number;
  likes: number;
  pipeline_tag: string;
  created_at: string;
  updated_at: string;
  pushed_at: string;
  scraped_at: string;
  query_used: string;
  type?: string;
  project_names?: string[];
  combination_rationale?: string;
};

type FindingsResponse = {
  total: number;
  returned: number;
  items: Finding[];
  last_updated: string | null;
};

type Stats = {
  total: number;
  by_source: Record<string, number>;
  by_grade: Record<string, number>;
  avg_score: number;
};

type ScheduleConfig = {
  enabled: boolean;
  github_enabled: boolean;
  gitlab_enabled: boolean;
  huggingface_enabled: boolean;
  interval_hours: number;
  scrape_time: string;
  github_queries: string[];
  gitlab_queries: string[];
  hf_queries: string[];
  min_stars_github: number;
  min_stars_gitlab: number;
  days_back: number;
  last_run: string | null;
  next_run: string | null;
  total_runs: number;
};

type SchedulerStatus = {
  running: boolean;
  scheduler_active: boolean;
  last_run: string | null;
  next_run: string | null;
  total_runs: number;
  interval_hours: number;
};

type InsightProject = {
  id: string;
  title: string;
  name: string;
  score: number;
  grade: string;
  url: string;
  iris_fit: string[];
  combination_rationale: string;
  project_names: string[];
  source: string;
};

type InsightSummary = {
  o_que_e: string;
  para_que_serve: string;
  onde_usariamos: string;
  o_que_implementariamos: string;
};

type ProductPotential = {
  score: number;
  viability: 'médio' | 'alto' | 'altíssimo';
  viability_color: string;
  viability_icon: string;
  viability_label: string;
  speed_impact: string;
  pitch: string;
};

type InsightImplementation = {
  status: string;
  implemented: boolean;
  confirmed_at: string | null;
  method: string | null;
  evidence: Record<string, unknown>;
  success_criteria: string[];
};

type InsightCategory = {
  category_id: string;
  title: string;
  description: string;
  color: string;
  icon: string;
  total_found: number;
  recommendation: string;
  summary?: InsightSummary;
  product_potential?: ProductPotential;
  implementation?: InsightImplementation;
  top_projects: InsightProject[];
};

type InsightsResponse = {
  insights: InsightCategory[];
  total_analyzed: number;
  generated_at: string;
};

type ProductFactoryMetrics = {
  total_products: number;
  by_repo_strategy: Record<string, number>;
  by_project_kind: Record<string, number>;
  provisioning_gate_pass_rate: number;
  github_push_rate: number;
  value_gate_pass_rate: number;
  average_value_score: number;
};

type ProductValueGate = {
  approved: boolean;
  score: number;
  failed_checks: string[];
  threshold: number;
};

type ProductRegistryItem = {
  category_id: string;
  application_name: string;
  application_slug: string;
  repo_strategy: string;
  project_kind: string;
  commit_sha: string;
  pushed_to_github: boolean;
  github_repo_url: string | null;
  product_value_gate?: ProductValueGate;
  provisioning_gate?: { approved: boolean; failed_checks: string[] };
  last_test_result?: ProductFactoryTestResult;
  created_at: string;
};

type ProductFactoryTestResult = {
  tested_at: string;
  test_kind: string;
  passed: boolean;
  validation: { command: string; result: string; output?: string }[];
};

type ProductRegistryResponse = {
  total: number;
  returned: number;
  items: ProductRegistryItem[];
};

type GitHubProvisioningStatus = {
  configured: boolean;
  authenticated: boolean;
  login: string;
  owner: string;
  standalone_repo_creation_ready: boolean;
  principal_repo_push_ready: boolean;
  blockers: { code: string; message: string }[];
  warnings: { code: string; message: string }[];
  gh_cli?: {
    available: boolean;
    authenticated: boolean;
    account: string;
    scopes: string[];
  };
};

type Props = { apiUrl: string };

// ─── Design tokens ────────────────────────────────────────────────────────────

const BORDER = 'rgba(255,255,255,0.08)';
const CARD_BG = 'rgba(255,255,255,0.03)';
const SCOUT_COLOR = '#38bdf8';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function gradeColor(grade: string): string {
  switch (grade) {
    case 'S': return '#fbbf24';
    case 'A': return '#22c55e';
    case 'B': return '#38bdf8';
    case 'C': return '#a78bfa';
    default:  return '#94a3b8';
  }
}

function sourceLabel(source: string): string {
  switch (source) {
    case 'github':           return 'GitHub';
    case 'gitlab':           return 'GitLab';
    case 'huggingface':      return 'HuggingFace';
    case 'huggingface_space':return 'HF Space';
    case 'combination':      return 'Combinação';
    default:                 return source;
  }
}

function sourceColor(source: string): string {
  switch (source) {
    case 'github':           return '#f0f6ff';
    case 'gitlab':           return '#fc6d26';
    case 'huggingface':      return '#fbbf24';
    case 'huggingface_space':return '#f97316';
    case 'combination':      return '#a78bfa';
    default:                 return '#94a3b8';
  }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('pt-BR', {
      day: '2-digit', month: '2-digit', year: '2-digit',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function scoreBar(value: number, max: number = 100): React.ReactNode {
  const pct = Math.min(100, (value / max) * 100);
  const color = value >= 70 ? '#fbbf24' : value >= 50 ? '#22c55e' : value >= 30 ? '#38bdf8' : '#94a3b8';
  return (
    <div style={{ height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.07)', overflow: 'hidden', flex: 1 }}>
      <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 999, transition: 'width 0.4s ease' }} />
    </div>
  );
}

function formatPercent(value: number | undefined): string {
  return `${Number(value ?? 0).toFixed(1)}%`;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

const Badge: React.FC<{ color: string; children: React.ReactNode }> = ({ color, children }) => (
  <span style={{
    display: 'inline-flex', alignItems: 'center',
    borderRadius: 999, border: `1px solid ${color}44`,
    background: `${color}12`, color,
    padding: '3px 9px', fontSize: 10, fontWeight: 700,
    letterSpacing: 0.8, textTransform: 'uppercase',
  }}>
    {children}
  </span>
);

const StatCard: React.FC<{ label: string; value: string | number; color?: string }> = ({ label, value, color = '#e2e8f0' }) => (
  <div style={{ borderRadius: 14, border: `1px solid ${BORDER}`, background: CARD_BG, padding: '14px 16px' }}>
    <div style={{ fontSize: 10, color: '#64748b', letterSpacing: 1.5, textTransform: 'uppercase' }}>{label}</div>
    <div style={{ marginTop: 6, fontSize: 22, fontWeight: 800, color }}>{value}</div>
  </div>
);

const FindingCard: React.FC<{ finding: Finding }> = ({ finding }) => {
  const gc = gradeColor(finding.grade);
  const sc = sourceColor(finding.source);
  const isCombination = finding.type === 'combination' || finding.source === 'combination';

  return (
    <div style={{
      borderRadius: 16,
      border: `1px solid ${isCombination ? 'rgba(167,139,250,0.25)' : BORDER}`,
      background: isCombination ? 'rgba(167,139,250,0.05)' : CARD_BG,
      padding: 16,
      transition: 'border-color 0.2s',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <Badge color={sc}>{sourceLabel(finding.source)}</Badge>
            {isCombination && <Badge color="#a78bfa">Combinação</Badge>}
            {finding.pipeline_tag && finding.pipeline_tag !== 'space' && (
              <Badge color="#64748b">{finding.pipeline_tag}</Badge>
            )}
          </div>
          <div style={{ marginTop: 8, fontSize: 15, fontWeight: 800, color: '#f8fafc', wordBreak: 'break-word' }}>
            {finding.title}
          </div>
          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
            {finding.name}
          </div>
        </div>

        {/* Grade badge */}
        <div style={{
          flexShrink: 0,
          width: 52, height: 52,
          borderRadius: 14,
          border: `2px solid ${gc}44`,
          background: `${gc}12`,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          gap: 2,
        }}>
          <div style={{ fontSize: 20, fontWeight: 900, color: gc }}>{finding.grade}</div>
          <div style={{ fontSize: 8, color: gc, letterSpacing: 0.5 }}>{finding.score}pts</div>
        </div>
      </div>

      {/* Score bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12 }}>
        <div style={{ fontSize: 11, color: '#64748b', minWidth: 52 }}>Score</div>
        {scoreBar(finding.score)}
        <div style={{ fontSize: 12, fontWeight: 700, color: gc, minWidth: 30 }}>{finding.score}</div>
      </div>

      {/* Description */}
      {finding.description && (
        <div style={{ marginTop: 10, fontSize: 12, color: '#94a3b8', lineHeight: 1.6, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
          {finding.description}
        </div>
      )}

      {/* Combination rationale */}
      {isCombination && finding.combination_rationale && (
        <div style={{
          marginTop: 10, padding: '8px 10px',
          borderRadius: 10, background: 'rgba(167,139,250,0.08)',
          border: '1px solid rgba(167,139,250,0.2)',
          fontSize: 11, color: '#c4b5fd', lineHeight: 1.5,
        }}>
          {finding.combination_rationale}
        </div>
      )}

      {/* Projetos combinados */}
      {isCombination && finding.project_names && finding.project_names.length > 0 && (
        <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {finding.project_names.map((name) => (
            <span key={name} style={{
              borderRadius: 8, background: 'rgba(167,139,250,0.1)',
              border: '1px solid rgba(167,139,250,0.2)',
              color: '#a78bfa', padding: '3px 8px', fontSize: 10, fontWeight: 600,
            }}>
              {name}
            </span>
          ))}
        </div>
      )}

      {/* IRIS Fit tags */}
      {finding.iris_fit.length > 0 && (
        <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {finding.iris_fit.map((tag) => (
            <span key={tag} style={{
              borderRadius: 8, background: 'rgba(56,189,248,0.08)',
              border: '1px solid rgba(56,189,248,0.2)',
              color: '#38bdf8', padding: '3px 8px', fontSize: 10, fontWeight: 600,
            }}>
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Stats row */}
      <div style={{ marginTop: 12, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        {finding.stars > 0 && (
          <div style={{ fontSize: 11, color: '#94a3b8' }}>★ {finding.stars.toLocaleString()}</div>
        )}
        {finding.downloads > 0 && (
          <div style={{ fontSize: 11, color: '#94a3b8' }}>↓ {finding.downloads.toLocaleString()}</div>
        )}
        {finding.likes > 0 && (
          <div style={{ fontSize: 11, color: '#94a3b8' }}>♥ {finding.likes.toLocaleString()}</div>
        )}
        {finding.language && finding.language !== 'N/A' && (
          <div style={{ fontSize: 11, color: '#64748b' }}>{finding.language}</div>
        )}
        <div style={{ marginLeft: 'auto', fontSize: 11, color: '#475569' }}>
          {formatDate(finding.scraped_at)}
        </div>

        {finding.url && (
          <a
            href={finding.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontSize: 11, color: SCOUT_COLOR,
              textDecoration: 'none', fontWeight: 600,
            }}
          >
            Ver projeto →
          </a>
        )}
      </div>

      {/* Score breakdown */}
      {Object.keys(finding.breakdown).length > 0 && (
        <details style={{ marginTop: 10 }}>
          <summary style={{ fontSize: 10, color: '#475569', cursor: 'pointer', letterSpacing: 0.8, textTransform: 'uppercase' }}>
            Score breakdown
          </summary>
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {Object.entries(finding.breakdown).map(([key, val]) => (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ fontSize: 10, color: '#64748b', minWidth: 120, textTransform: 'capitalize' }}>
                  {key.replace(/_/g, ' ')}
                </div>
                {scoreBar(val, 30)}
                <div style={{ fontSize: 10, color: '#94a3b8', minWidth: 20 }}>{val}</div>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
};

// ─── Schedule Config Panel ─────────────────────────────────────────────────────

const SchedulePanel: React.FC<{
  apiUrl: string;
  config: ScheduleConfig | null;
  status: SchedulerStatus | null;
  scraping: boolean;
  onScrapeNow: () => void;
  onRefresh: () => void;
}> = ({ apiUrl, config, status, scraping, onScrapeNow, onRefresh }) => {
  const [form, setForm] = useState<Partial<ScheduleConfig>>({});
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  useEffect(() => {
    if (config) setForm(config);
  }, [config]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveMsg('');
    try {
      const resp = await fetch(`${apiUrl}/research/schedule`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enabled: form.enabled,
          github_enabled: form.github_enabled,
          gitlab_enabled: form.gitlab_enabled,
          huggingface_enabled: form.huggingface_enabled,
          interval_hours: form.interval_hours,
          scrape_time: form.scrape_time,
          min_stars_github: form.min_stars_github,
          min_stars_gitlab: form.min_stars_gitlab,
          days_back: form.days_back,
          github_queries: form.github_queries,
          gitlab_queries: form.gitlab_queries,
          hf_queries: form.hf_queries,
        }),
      });
      if (!resp.ok) throw new Error(`Falha (${resp.status})`);
      setSaveMsg('Salvo com sucesso!');
      onRefresh();
    } catch (e) {
      setSaveMsg(`Erro: ${e instanceof Error ? e.message : 'desconhecido'}`);
    } finally {
      setSaving(false);
    }
  }, [apiUrl, form, onRefresh]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Status card */}
      <div style={{
        padding: 16, borderRadius: 16, border: `1px solid ${BORDER}`,
        background: 'linear-gradient(180deg, rgba(12,12,22,0.94), rgba(8,8,18,0.92))',
      }}>
        <div style={{ fontSize: 10, color: SCOUT_COLOR, letterSpacing: 2, textTransform: 'uppercase' }}>
          ◈ Intel Scout
        </div>
        <div style={{ marginTop: 6, fontSize: 18, fontWeight: 800, color: '#f8fafc' }}>
          SCOUT-01
        </div>
        <div style={{ marginTop: 4, fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
          Especialista em inteligência técnica — raspa GitHub, GitLab e HuggingFace em busca de projetos altamente promissores.
        </div>

        <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <StatusRow label="Status" value={status?.running ? 'Raspando...' : 'Aguardando'} ok={!status?.running} />
          <StatusRow label="Scheduler" value={status?.scheduler_active ? 'Ativo' : 'Inativo'} ok={status?.scheduler_active} />
          <StatusRow label="Último run" value={formatDate(status?.last_run)} ok={!!status?.last_run} />
          <StatusRow label="Próximo run" value={formatDate(status?.next_run)} ok={!!status?.next_run} />
          <StatusRow label="Total de runs" value={String(status?.total_runs ?? 0)} ok />
        </div>
      </div>

      {/* Scrape now button */}
      <button
        onClick={onScrapeNow}
        disabled={scraping || status?.running}
        style={{
          border: 'none', borderRadius: 14, padding: '14px 16px',
          background: scraping || status?.running
            ? 'rgba(56,189,248,0.3)'
            : 'linear-gradient(135deg, #38bdf8, #0284c7)',
          color: '#f8fafc', fontWeight: 800, fontSize: 14,
          letterSpacing: 0.4, cursor: scraping ? 'wait' : 'pointer',
          transition: 'all 0.2s',
        }}
      >
        {scraping || status?.running ? '⏳ Raspando...' : '⚡ Raspar Agora'}
      </button>

      {/* Config form */}
      <div style={{
        padding: 16, borderRadius: 16, border: `1px solid ${BORDER}`,
        background: 'rgba(9,11,20,0.96)', display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        <div style={{ fontSize: 10, color: '#94a3b8', letterSpacing: 2, textTransform: 'uppercase' }}>
          Configuração de Agendamento
        </div>

        {/* Toggles */}
        <ToggleRow
          label="Scheduler ativo"
          value={form.enabled ?? true}
          onChange={(v) => setForm((f) => ({ ...f, enabled: v }))}
        />
        <ToggleRow
          label="GitHub"
          value={form.github_enabled ?? true}
          onChange={(v) => setForm((f) => ({ ...f, github_enabled: v }))}
        />
        <ToggleRow
          label="GitLab"
          value={form.gitlab_enabled ?? true}
          onChange={(v) => setForm((f) => ({ ...f, gitlab_enabled: v }))}
        />
        <ToggleRow
          label="HuggingFace"
          value={form.huggingface_enabled ?? true}
          onChange={(v) => setForm((f) => ({ ...f, huggingface_enabled: v }))}
        />

        {/* Interval */}
        <div>
          <label style={labelStyle}>Intervalo (horas)</label>
          <input
            type="number"
            min={1} max={168}
            value={form.interval_hours ?? 6}
            onChange={(e) => setForm((f) => ({ ...f, interval_hours: Number(e.target.value) }))}
            style={inputStyle}
          />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div>
            <label style={labelStyle}>Horário preferido</label>
            <input
              type="time"
              value={form.scrape_time ?? '08:00'}
              onChange={(e) => setForm((f) => ({ ...f, scrape_time: e.target.value }))}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={labelStyle}>Stars mínimas (GitHub)</label>
            <input
              type="number" min={0}
              value={form.min_stars_github ?? 50}
              onChange={(e) => setForm((f) => ({ ...f, min_stars_github: Number(e.target.value) }))}
              style={inputStyle}
            />
          </div>
          <div>
            <label style={labelStyle}>Stars mínimas (GitLab)</label>
            <input
              type="number" min={0}
              value={form.min_stars_gitlab ?? 25}
              onChange={(e) => setForm((f) => ({ ...f, min_stars_gitlab: Number(e.target.value) }))}
              style={inputStyle}
            />
          </div>
        </div>

        <div>
          <label style={labelStyle}>Dias para trás</label>
          <input
            type="number" min={7} max={365}
            value={form.days_back ?? 30}
            onChange={(e) => setForm((f) => ({ ...f, days_back: Number(e.target.value) }))}
            style={inputStyle}
          />
        </div>

        {/* GitHub queries */}
        <div>
          <label style={labelStyle}>Queries GitHub (uma por linha)</label>
          <textarea
            rows={5}
            value={(form.github_queries ?? []).join('\n')}
            onChange={(e) => setForm((f) => ({ ...f, github_queries: e.target.value.split('\n').filter(Boolean) }))}
            style={{ ...inputStyle, resize: 'vertical', minHeight: 100 }}
          />
        </div>

        <div>
          <label style={labelStyle}>Queries GitLab (uma por linha)</label>
          <textarea
            rows={4}
            value={(form.gitlab_queries ?? []).join('\n')}
            onChange={(e) => setForm((f) => ({ ...f, gitlab_queries: e.target.value.split('\n').filter(Boolean) }))}
            style={{ ...inputStyle, resize: 'vertical', minHeight: 80 }}
          />
        </div>

        {/* HF queries */}
        <div>
          <label style={labelStyle}>Queries HuggingFace (uma por linha)</label>
          <textarea
            rows={4}
            value={(form.hf_queries ?? []).join('\n')}
            onChange={(e) => setForm((f) => ({ ...f, hf_queries: e.target.value.split('\n').filter(Boolean) }))}
            style={{ ...inputStyle, resize: 'vertical', minHeight: 80 }}
          />
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            border: `1px solid ${SCOUT_COLOR}44`, borderRadius: 12,
            padding: '11px 14px', background: `${SCOUT_COLOR}10`,
            color: SCOUT_COLOR, fontWeight: 700, cursor: saving ? 'wait' : 'pointer',
          }}
        >
          {saving ? 'Salvando...' : 'Salvar configuração'}
        </button>

        {saveMsg && (
          <div style={{ fontSize: 12, color: saveMsg.startsWith('Erro') ? '#fca5a5' : '#22c55e' }}>
            {saveMsg}
          </div>
        )}
      </div>
    </div>
  );
};

// ─── Small helpers ─────────────────────────────────────────────────────────────

const StatusRow: React.FC<{ label: string; value: string; ok?: boolean }> = ({ label, value, ok }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
    <div style={{ fontSize: 11, color: '#64748b' }}>{label}</div>
    <div style={{ fontSize: 11, fontWeight: 600, color: ok ? '#94a3b8' : '#ef4444' }}>{value}</div>
  </div>
);

const ToggleRow: React.FC<{ label: string; value: boolean; onChange: (v: boolean) => void }> = ({ label, value, onChange }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
    <div style={{ fontSize: 12, color: '#cbd5e1' }}>{label}</div>
    <button
      type="button"
      onClick={() => onChange(!value)}
      style={{
        borderRadius: 999, padding: '5px 14px',
        background: value ? 'rgba(56,189,248,0.15)' : 'rgba(255,255,255,0.05)',
        color: value ? SCOUT_COLOR : '#64748b',
        fontWeight: 700, fontSize: 11, cursor: 'pointer',
        border: `1px solid ${value ? `${SCOUT_COLOR}44` : 'transparent'}`,
      }}
    >
      {value ? 'ON' : 'OFF'}
    </button>
  </div>
);

const labelStyle: React.CSSProperties = {
  display: 'block', marginBottom: 6,
  fontSize: 10, color: '#64748b', letterSpacing: 1.2, textTransform: 'uppercase',
};

const inputStyle: React.CSSProperties = {
  width: '100%', borderRadius: 10,
  border: '1px solid rgba(255,255,255,0.08)',
  background: 'rgba(255,255,255,0.04)',
  color: '#f8fafc', padding: '10px 12px',
  outline: 'none', fontSize: 13,
};

// ─── Insights Modal ───────────────────────────────────────────────────────────

function buildTaskPrompt(cat: InsightCategory): string {
  const top = cat.top_projects[0];
  const projectList = cat.top_projects
    .map((p, i) => `${i + 1}. **${p.title}** (${p.name}) — Score ${p.score} | Grade ${p.grade}${p.url ? ` | ${p.url}` : ''}${p.iris_fit.length ? `\n   IRIS Fit: ${p.iris_fit.join(', ')}` : ''}`)
    .join('\n');

  return `# INTEGRAÇÃO IRIS · ${cat.icon} ${cat.title}

## Contexto Estratégico
${cat.description}
Total de ${cat.total_found} projetos identificados pelo agente SCOUT-01 (Intel Hub) via raspagem GitHub + GitLab + HuggingFace.

## Diretriz Principal
${cat.recommendation}

## Projeto Prioritário (Top #1)
**${top.title}** — Grade ${top.grade} | Score ${top.score}
- Repositório: ${top.name}
${top.url ? `- URL: ${top.url}` : ''}
- IRIS Fit: ${top.iris_fit.join(', ')}
${top.combination_rationale ? `- Sinergia: ${top.combination_rationale}` : ''}

## Top ${cat.top_projects.length} Projetos Para Análise
${projectList}

## Stack IRIS (Contexto de Integração)
- Backend: Python 3.12, FastAPI (async), Pydantic v2
- Agentes: CrewAI + LangGraph (dev_orchestrator, marketing_orchestrator)
- MCP Bridge: PicoClaw (http://127.0.0.1:18790) — gateway para ferramentas externas
- LLMs: OpenRouter (free models) + Ollama local (qwen2.5-coder:32b, qwen2.5:7b)
- Eventos: Redis EventBus (pub/sub entre agentes)
- Persistência: Supabase + .runtime/ JSON

## Tarefas Técnicas (Padrão Gold — Nível PhD Eng. Software)

### Fase 1 — Análise Técnica
- Avaliar licença, dependências e compatibilidade com Python 3.12 / asyncio
- Mapear APIs públicas, pontos de extensão e padrões arquiteturais do projeto
- Identificar riscos: segurança, performance, breaking changes futuros

### Fase 2 — Integração IRIS
- Criar ferramenta (Tool class) callable pelos agentes existentes OU endpoint FastAPI
- Implementar como MCP Tool via PicoClaw se aplicável
- Garantir compatibilidade com o EventBus (emitir eventos de progresso)
- Respeitar padrões: async/await, typed hints, schemas Pydantic

### Fase 3 — Qualidade
- Smoke test funcional + teste de integração no pipeline de agentes
- Verificar ausência de regressões nos endpoints /health, /tasks, /research
- Code coverage mínimo: lógica de negócio crítica

### Fase 4 — Documentação e Entrega
- Docstring nas classes/funções principais
- Guia de uso: como um agente invoca a nova ferramenta
- Exemplo de output esperado

## Critérios de Aceite
- [ ] Integração funcional e demonstrável no ambiente local
- [ ] Zero quebra de funcionalidades existentes
- [ ] Código segue padrões IRIS (async, typed, Pydantic)
- [ ] Ferramenta registrada e disponível para os agentes IRIS
- [ ] Evidência de funcionamento: log ou output capturado

**Fonte:** Intel Hub SCOUT-01 — ${new Date().toLocaleDateString('pt-BR')}`;
}

const SUMMARY_KEYS = [
  { key: 'o_que_e'               as const, label: 'O QUE É',               emoji: '📌' },
  { key: 'para_que_serve'        as const, label: 'PARA QUE SERVE',        emoji: '🎯' },
  { key: 'onde_usariamos'        as const, label: 'ONDE USARÍAMOS',        emoji: '🏗️' },
  { key: 'o_que_implementariamos'as const, label: 'O QUE IMPLEMENTARÍAMOS',emoji: '⚙️' },
];

// ─── Execution log types ─────────────────────────────────────────────────────

type LogEntry = { timestamp: string; message: string; agent_id?: string; agent_role?: string };
type TeamTask = {
  task_id: string | null;
  status: 'idle' | 'queued' | 'running' | 'done' | 'failed';
  logs: LogEntry[];
  reportPath: string | null;
  githubUrl: string | null;
  qualityApproved?: boolean;
};
type CategoryExecution = { dev: TeamTask; marketing: TeamTask };

// ─── Marketing prompt builder ─────────────────────────────────────────────────

function buildMarketingPrompt(cat: InsightCategory): string {
  const projectList = cat.top_projects
    .slice(0, 5)
    .map((p, i) => `${i + 1}. **${p.title}** — Score ${p.score} | Grade ${p.grade}`)
    .join('\n');
  const pp = cat.product_potential;

  return `# ANÁLISE COMERCIAL IRIS · ${cat.icon} ${cat.title}

## Oportunidade de Mercado
${cat.description}
${pp ? `Viabilidade de produto: **${pp.viability.toUpperCase()}** (${pp.score}/100)\n${pp.pitch}` : ''}

## Impacto Estratégico
${pp?.speed_impact ?? cat.recommendation}

## Top Projetos Para Posicionamento de Mercado
${projectList}

## Tarefas de Marketing & Produto (Padrão Gold — CMO / Growth)

### Fase 1 — Análise de Mercado
- Pesquisar concorrentes e soluções similares no mercado atual
- Mapear público-alvo: segmentos, dores, willingness to pay
- Benchmarking de preços e modelos de negócio (SaaS, API, on-premise)

### Fase 2 — Proposta de Valor
- Elaborar unique value proposition (UVP) diferenciada
- Criar messaging framework: headlines, taglines, elevator pitch
- Definir pricing strategy: tiers, freemium, enterprise

### Fase 3 — Go-to-Market
- Plano de lançamento: canais, timing, público early-adopters
- Estratégia de conteúdo: blog, demos, case studies
- Pipeline de leads: outbound, inbound, partnerships

### Fase 4 — Métricas & KPIs
- Definir North Star Metric para este produto
- Dashboard de acompanhamento: CAC, LTV, churn, NPS
- Projeções de receita: 6m, 12m, 24m

## Critérios de Aceite
- [ ] Análise competitiva documentada
- [ ] UVP e messaging framework criados
- [ ] Plano go-to-market com cronograma
- [ ] Projeção financeira básica (TAM, SAM, SOM)
- [ ] Material de apresentação para stakeholders

**Fonte:** Intel Hub SCOUT-01 — ${new Date().toLocaleDateString('pt-BR')}`;
}

// ─── Team log panel ───────────────────────────────────────────────────────────

function LogPanel({ team, color, task, catColor }: { team: string; color: string; task: TeamTask; catColor?: string }) {
  const logRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [task.logs.length]);

  const statusColor =
    task.status === 'done' ? '#22c55e' :
    task.status === 'failed' ? '#f87171' :
    task.status === 'running' ? color : '#94a3b8';
  const statusLabel =
    task.status === 'idle' ? '○ Aguardando' :
    task.status === 'queued' ? '◌ Na fila' :
    task.status === 'running' ? '● Executando' :
    task.status === 'done' ? '✓ Concluído' : '✗ Falhou';

  return (
    <div style={{ borderRadius: 18, overflow: 'hidden', border: `1px solid ${color}20`, background: 'rgba(0,0,0,0.45)' }}>
      <div style={{ height: 3, background: `linear-gradient(90deg, ${color}, transparent)` }} />
      <div style={{ padding: '12px 16px', borderBottom: `1px solid ${color}12`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%', background: statusColor,
            boxShadow: task.status === 'running' ? `0 0 8px ${color}` : 'none',
            transition: 'box-shadow 0.3s',
          }} />
          <span style={{ fontSize: 11, fontWeight: 800, color, letterSpacing: 1.5 }}>TIME {team}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 9, fontWeight: 700, color: statusColor }}>{statusLabel}</span>
          {task.task_id && (
            <span style={{ fontSize: 8, color: '#334155', fontFamily: 'monospace' }}>{task.task_id.slice(0, 8)}…</span>
          )}
        </div>
      </div>
      <div ref={logRef} style={{ height: task.reportPath ? 150 : 200, overflowY: 'auto', padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 5 }}>
        {task.logs.length === 0 ? (
          <div style={{ color: '#334155', fontSize: 11, fontStyle: 'italic', marginTop: 6 }}>
            {task.task_id ? 'Aguardando primeiros logs...' : 'Task não iniciada.'}
          </div>
        ) : (
          task.logs.map((entry, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              <span style={{ fontSize: 8, color: '#334155', flexShrink: 0, fontFamily: 'monospace', marginTop: 2 }}>
                {new Date(entry.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              {entry.agent_role && (
                <span style={{ fontSize: 9, fontWeight: 700, color: `${color}99`, flexShrink: 0, marginTop: 1 }}>
                  [{entry.agent_role}]
                </span>
              )}
              <span style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.5 }}>{entry.message}</span>
            </div>
          ))
        )}
      </div>

      {/* Report saved banner */}
      {task.reportPath && (
        <div style={{
          borderTop: `1px solid ${catColor ?? '#22c55e'}22`,
          padding: '10px 14px',
          background: `linear-gradient(90deg, ${catColor ?? '#22c55e'}0c, transparent)`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 13 }}>✓</span>
              <span style={{ fontSize: 9, fontWeight: 800, color: '#22c55e', letterSpacing: 1.2 }}>RELATÓRIO SALVO</span>
            </div>
            {task.githubUrl && (
              <a
                href={task.githubUrl}
                target="_blank"
                rel="noreferrer"
                style={{
                  fontSize: 9, fontWeight: 700, color: '#f0f6ff', letterSpacing: 0.8,
                  background: 'rgba(240,246,255,0.08)', border: '1px solid rgba(240,246,255,0.18)',
                  borderRadius: 5, padding: '3px 8px', textDecoration: 'none',
                  display: 'flex', alignItems: 'center', gap: 4,
                }}
              >
                ↗ GitHub
              </a>
            )}
          </div>
          <div style={{
            fontSize: 9, color: '#475569', fontFamily: 'monospace',
            wordBreak: 'break-all', lineHeight: 1.6, marginTop: 5,
            background: 'rgba(0,0,0,0.3)', borderRadius: 6, padding: '6px 8px',
          }}>
            {task.reportPath}
          </div>
          {!task.githubUrl && (
            <div style={{ marginTop: 5, fontSize: 9, color: '#334155' }}>
              Abra no explorador de arquivos para ver o relatório completo + README.md
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ViabilityBar({ score, color }: { score: number; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${score}%`, borderRadius: 999, background: `linear-gradient(90deg, ${color}99, ${color})`, transition: 'width 0.6s ease' }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 800, color, minWidth: 28 }}>{score}</span>
    </div>
  );
}

const InsightsModal: React.FC<{
  data: InsightsResponse;
  apiUrl: string;
  onClose: () => void;
}> = ({ data, apiUrl, onClose }) => {
  const [executing, setExecuting] = useState<string | null>(null);
  const [promoting, setPromoting] = useState<string | null>(null);
  const [promotionResult, setPromotionResult] = useState<Record<string, string>>({});
  const [creatingApp, setCreatingApp] = useState<string | null>(null);
  const [applicationResult, setApplicationResult] = useState<Record<string, string>>({});
  const [executions, setExecutions] = useState<Record<string, CategoryExecution>>({});
  const [factoryMetrics, setFactoryMetrics] = useState<ProductFactoryMetrics | null>(null);
  const [factoryRegistry, setFactoryRegistry] = useState<ProductRegistryItem[]>([]);
  const [githubStatus, setGithubStatus] = useState<GitHubProvisioningStatus | null>(null);
  const [testingImplementation, setTestingImplementation] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, string>>({});
  const [implementations, setImplementations] = useState<Record<string, InsightImplementation>>(
    Object.fromEntries(data.insights.map((item) => [item.category_id, item.implementation]).filter(([, value]) => Boolean(value))) as Record<string, InsightImplementation>,
  );
  const [selected, setSelected] = useState<string>(data.insights[0]?.category_id ?? '');

  useEffect(() => {
    setImplementations(
      Object.fromEntries(data.insights.map((item) => [item.category_id, item.implementation]).filter(([, value]) => Boolean(value))) as Record<string, InsightImplementation>,
    );
  }, [data]);

  const cat = data.insights.find((c) => c.category_id === selected) ?? data.insights[0];
  const currentImplementation = cat ? (implementations[cat.category_id] ?? cat.implementation) : undefined;
  const isImplemented = !!currentImplementation?.implemented;
  const currentProduct = cat
    ? factoryRegistry.find((item) => item.category_id === cat.category_id)
    : undefined;
  const githubReady = Boolean(githubStatus?.standalone_repo_creation_ready);

  const refreshFactoryStatus = useCallback(async () => {
    const [metricsResp, registryResp, githubResp] = await Promise.all([
      fetch(`${apiUrl}/product-factory/metrics`).catch(() => null),
      fetch(`${apiUrl}/product-factory/registry?limit=50`).catch(() => null),
      fetch(`${apiUrl}/integrations/github`).catch(() => null),
    ]);
    if (metricsResp?.ok) {
      setFactoryMetrics(await metricsResp.json() as ProductFactoryMetrics);
    }
    if (registryResp?.ok) {
      const registry = await registryResp.json() as ProductRegistryResponse;
      setFactoryRegistry(registry.items ?? []);
    }
    if (githubResp?.ok) {
      setGithubStatus(await githubResp.json() as GitHubProvisioningStatus);
    }
  }, [apiUrl]);

  useEffect(() => {
    refreshFactoryStatus();
    const id = window.setInterval(refreshFactoryStatus, 15000);
    return () => window.clearInterval(id);
  }, [refreshFactoryStatus]);

  const confirmImplemented = useCallback(async (
    cat: InsightCategory,
    method: string,
    evidence: Record<string, unknown>,
  ) => {
    const resp = await fetch(`${apiUrl}/research/insights/${cat.category_id}/confirm-implemented`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ method, evidence }),
    });
    const json = await resp.json().catch(() => null);
    if (!resp.ok) throw new Error(json?.detail || `Falha HTTP ${resp.status}`);
    setImplementations(prev => ({ ...prev, [cat.category_id]: json as InsightImplementation }));
    return json as InsightImplementation;
  }, [apiUrl]);

  // Poll logs + status for both teams while tasks are in-flight
  useEffect(() => {
    const devId = executions[selected]?.dev?.task_id ?? null;
    const mktId = executions[selected]?.marketing?.task_id ?? null;
    if (!devId && !mktId) return;

    const poll = async () => {
      for (const [team, tid] of [['dev', devId], ['marketing', mktId]] as [string, string | null][]) {
        if (!tid) continue;
        const [sRes, lRes] = await Promise.all([
          fetch(`${apiUrl}/tasks/${tid}`).catch(() => null),
          fetch(`${apiUrl}/tasks/${tid}/execution-log`).catch(() => null),
        ]);
        const sJson = sRes?.ok ? await sRes.json().catch(() => null) : null;
        const lJson = lRes?.ok ? await lRes.json().catch(() => null) : null;
        if (sJson || lJson) {
          const qualityApproved = Boolean(sJson?.quality_approved);
          const newStatus: string = sJson?.final_output
            ? (qualityApproved ? 'done' : 'failed')
            : (sJson ? 'running' : '');
          let reportPath: string | null = null;
          let githubUrl: string | null = null;
          if (sJson?.final_output && tid) {
            try {
              const rRes = await fetch(`${apiUrl}/tasks/${tid}/report`);
              if (rRes.ok) {
                const rJson = await rRes.json();
                if (rJson.exists) reportPath = rJson.path;
                if (rJson.github_url) githubUrl = rJson.github_url;
              }
            } catch { /* non-blocking */ }
          }
          setExecutions(prev => {
            const current = prev[selected]?.[team as 'dev' | 'marketing'];
            if (!current) return prev;
            return {
              ...prev,
              [selected]: {
                ...prev[selected],
                [team]: {
                  ...current,
                  status: (newStatus || current.status) as TeamTask['status'],
                  logs: lJson?.items ?? current.logs,
                  reportPath: reportPath ?? current.reportPath,
                  githubUrl: githubUrl ?? current.githubUrl,
                  qualityApproved,
                },
              },
            };
          });
        }
      }
    };

    poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, [executions[selected]?.dev?.task_id, executions[selected]?.marketing?.task_id, selected, apiUrl]);

  useEffect(() => {
    if (!cat || isImplemented) return;
    const exec = executions[cat.category_id];
    if (!exec?.dev?.task_id || !exec?.marketing?.task_id) return;
    if (!exec.dev.qualityApproved || !exec.marketing.qualityApproved) return;
    if (!exec.dev.reportPath || !exec.marketing.reportPath) return;

    confirmImplemented(cat, 'agent_execution', {
      dev_task_id: exec.dev.task_id,
      marketing_task_id: exec.marketing.task_id,
      dev_report_path: exec.dev.reportPath,
      marketing_report_path: exec.marketing.reportPath,
    }).catch((error) => {
      setPromotionResult(prev => ({
        ...prev,
        [cat.category_id]: `Falha ao confirmar implementação: ${error instanceof Error ? error.message : 'erro desconhecido'}`,
      }));
    });
  }, [cat, executions, isImplemented, confirmImplemented]);

  const handleExecute = async (cat: InsightCategory) => {
    setExecuting(cat.category_id);
    const blank: TeamTask = { task_id: null, status: 'queued', logs: [], reportPath: null, githubUrl: null };
    setExecutions(prev => ({ ...prev, [cat.category_id]: { dev: { ...blank }, marketing: { ...blank } } }));

    const [devResp, mktResp] = await Promise.all([
      fetch(`${apiUrl}/tasks/dev`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request: buildTaskPrompt(cat), priority: 1 }),
      }).catch(() => null),
      fetch(`${apiUrl}/tasks/marketing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request: buildMarketingPrompt(cat), priority: 1 }),
      }).catch(() => null),
    ]);

    const devJson = devResp?.ok ? await devResp.json().catch(() => null) : null;
    const mktJson = mktResp?.ok ? await mktResp.json().catch(() => null) : null;

    setExecutions(prev => ({
      ...prev,
      [cat.category_id]: {
        dev: { task_id: devJson?.task_id ?? null, status: devJson?.task_id ? 'queued' : 'failed', logs: [], reportPath: null, githubUrl: null },
        marketing: { task_id: mktJson?.task_id ?? null, status: mktJson?.task_id ? 'queued' : 'failed', logs: [], reportPath: null, githubUrl: null },
      },
    }));
    setExecuting(null);
  };

  const handlePromote = async (cat: InsightCategory) => {
    setPromoting(cat.category_id);
    try {
      const resp = await fetch(`${apiUrl}/research/insights/${cat.category_id}/promote`, { method: 'POST' });
      const json = await resp.json().catch(() => null);
      if (!resp.ok) throw new Error(json?.detail || `Falha HTTP ${resp.status}`);
      setPromotionResult(prev => ({
        ...prev,
        [cat.category_id]: `Commit ${json.commit_sha} · ${json.repo_relative_path}${json.pushed_to_github ? ' · GitHub atualizado' : ''}`,
      }));
      if (json.implementation) {
        setImplementations(prev => ({ ...prev, [cat.category_id]: json.implementation as InsightImplementation }));
      }
      refreshFactoryStatus();
    } catch (e) {
      setPromotionResult(prev => ({
        ...prev,
        [cat.category_id]: `Falha ao promover: ${e instanceof Error ? e.message : 'erro desconhecido'}`,
      }));
    } finally {
      setPromoting(null);
    }
  };

  const handleCreateApplication = async (cat: InsightCategory) => {
    setCreatingApp(cat.category_id);
    try {
      const resp = await fetch(`${apiUrl}/research/insights/${cat.category_id}/create-application`, { method: 'POST' });
      const json = await resp.json().catch(() => null);
      if (!resp.ok) throw new Error(json?.detail || `Falha HTTP ${resp.status}`);
      const repoSummary = json?.repo_strategy === 'dedicated_repository'
        ? `repo dedicado ${json?.github_repo_url || ''}`.trim()
        : 'repo IRIS';
      setApplicationResult(prev => ({
        ...prev,
        [cat.category_id]: `App ${json.application_slug} · commit ${json.commit_sha} · ${repoSummary}${json.pushed_to_github ? ' · GitHub atualizado' : ''}`,
      }));
      if (json.implementation) {
        setImplementations(prev => ({ ...prev, [cat.category_id]: json.implementation as InsightImplementation }));
      }
      refreshFactoryStatus();
    } catch (e) {
      setApplicationResult(prev => ({
        ...prev,
        [cat.category_id]: `Falha ao criar app: ${e instanceof Error ? e.message : 'erro desconhecido'}`,
      }));
    } finally {
      setCreatingApp(null);
    }
  };

  const handleTestImplementation = async (cat: InsightCategory) => {
    setTestingImplementation(cat.category_id);
    setTestResult(prev => ({ ...prev, [cat.category_id]: 'Executando testes objetivos...' }));
    try {
      const resp = await fetch(`${apiUrl}/product-factory/${cat.category_id}/test`, { method: 'POST' });
      const json = await resp.json().catch(() => null);
      if (!resp.ok) throw new Error(json?.detail || `Falha HTTP ${resp.status}`);
      const result = json.test_result as ProductFactoryTestResult;
      setTestResult(prev => ({
        ...prev,
        [cat.category_id]: `${result.passed ? 'Teste aprovado' : 'Teste reprovado'} · ${result.test_kind} · ${result.validation?.length ?? 0} checks`,
      }));
      refreshFactoryStatus();
    } catch (e) {
      setTestResult(prev => ({
        ...prev,
        [cat.category_id]: `Falha ao testar: ${e instanceof Error ? e.message : 'erro desconhecido'}`,
      }));
    } finally {
      setTestingImplementation(null);
    }
  };

  if (!cat) return null;
  const exec = executions[cat.category_id];
  const isExec = executing === cat.category_id;
  const dispatched = !!(exec?.dev?.task_id || exec?.marketing?.task_id);
  const pp = cat.product_potential;

  /* ─── Full-screen layout ─── */
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: '#06080e',
      display: 'flex', flexDirection: 'column',
    }}>

      {/* ══ NAVBAR ════════════════════════════════════════════════════════════ */}
      <nav style={{
        flexShrink: 0, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px', gap: 20,
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: 'linear-gradient(90deg,rgba(56,189,248,0.07) 0%,rgba(6,8,14,0.98) 40%)',
      }}>
        {/* Left: back button + logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 14px', borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.09)',
              background: 'rgba(255,255,255,0.04)',
              color: '#94a3b8', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}
          >
            ← Intel Hub
          </button>
          <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.07)' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: SCOUT_COLOR, boxShadow: `0 0 10px ${SCOUT_COLOR}` }} />
            <span style={{ fontSize: 11, fontWeight: 800, color: '#e2e8f0', letterSpacing: 0.3 }}>
              IRIS Intelligence Report
            </span>
            <span style={{ fontSize: 10, color: '#334155', letterSpacing: 1 }}>· SCOUT-01</span>
          </div>
        </div>

        {/* Center: page title */}
        <div style={{
          fontSize: 15, fontWeight: 900, letterSpacing: -0.2,
          background: 'linear-gradient(120deg,#f1f5f9 30%,#7dd3fc 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        }}>
          Insights de Evolução & Produto
        </div>

        {/* Right: stats */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#e2e8f0' }}>{data.total_analyzed} projetos</div>
            <div style={{ fontSize: 9, color: '#334155' }}>{formatDate(data.generated_at)}</div>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {data.insights.map((c) => (
              <div
                key={c.category_id}
                title={c.title}
                style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: c.color,
                  opacity: c.category_id === selected ? 1 : 0.3,
                  boxShadow: c.category_id === selected ? `0 0 8px ${c.color}` : 'none',
                  transition: 'all 0.2s', cursor: 'pointer',
                }}
                onClick={() => setSelected(c.category_id)}
              />
            ))}
          </div>
        </div>
      </nav>

      {/* ══ BODY ══════════════════════════════════════════════════════════════ */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>

        {/* ── SIDEBAR ──────────────────────────────────────────────────────── */}
        <aside style={{
          width: 300, flexShrink: 0,
          display: 'flex', flexDirection: 'column',
          borderRight: '1px solid rgba(255,255,255,0.05)',
          background: 'rgba(0,0,0,0.35)',
          overflowY: 'auto',
        }}>
          {/* Sidebar header */}
          <div style={{
            padding: '18px 20px 12px',
            borderBottom: '1px solid rgba(255,255,255,0.04)',
          }}>
            <div style={{ fontSize: 9, color: '#334155', letterSpacing: 2.5, textTransform: 'uppercase', fontWeight: 700 }}>
              {data.insights.length} Categorias Analisadas
            </div>
            <div style={{ marginTop: 6, fontSize: 12, color: '#475569', lineHeight: 1.5 }}>
              Selecione uma categoria para ver análise completa e potencial comercial
            </div>
          </div>

          {/* Category items */}
          <div style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
            {data.insights.map((c) => {
              const isActive = c.category_id === selected;
              const cExec = executions[c.category_id];
              const cPP = c.product_potential;
              const cImplementation = implementations[c.category_id] ?? c.implementation;
              return (
                <button
                  key={c.category_id}
                  type="button"
                  onClick={() => setSelected(c.category_id)}
                  style={{
                    textAlign: 'left', padding: '14px 16px', border: 'none',
                    borderRadius: 16, cursor: 'pointer', transition: 'all 0.15s',
                    background: isActive
                      ? `linear-gradient(135deg, ${c.color}1a 0%, rgba(6,8,14,0.96) 100%)`
                      : 'rgba(255,255,255,0.02)',
                    outline: isActive ? `1.5px solid ${c.color}40` : '1.5px solid transparent',
                    position: 'relative', overflow: 'hidden',
                  }}
                >
                  {/* Left accent bar */}
                  {isActive && (
                    <div style={{
                      position: 'absolute', left: 0, top: 0, bottom: 0,
                      width: 3, background: c.color,
                      borderRadius: '3px 0 0 3px',
                    }} />
                  )}

                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingLeft: isActive ? 4 : 0 }}>
                    {/* Icon */}
                    <div style={{
                      width: 40, height: 40, borderRadius: 14, flexShrink: 0,
                      background: isActive
                        ? `radial-gradient(circle, ${c.color}30, ${c.color}12)`
                        : 'rgba(255,255,255,0.05)',
                      border: `1px solid ${isActive ? c.color + '45' : 'rgba(255,255,255,0.07)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 20, transition: 'all 0.15s',
                      boxShadow: isActive ? `0 0 20px ${c.color}25` : 'none',
                    }}>
                      {c.icon}
                    </div>

                    {/* Info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: isActive ? '#f1f5f9' : '#94a3b8', lineHeight: 1.2 }}>
                        {c.title}
                      </div>
                      <div style={{ fontSize: 10, color: isActive ? c.color + 'cc' : '#475569', marginTop: 3 }}>
                        {c.total_found} projetos identificados
                      </div>
                    </div>

                    {/* Status badge */}
                    {cImplementation?.implemented ? (
                      <div style={{
                        width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
                        background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.4)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 9, color: '#22c55e', fontWeight: 900,
                      }} title="Insight implementado">✓</div>
                    ) : cExec?.dev?.reportPath || cExec?.marketing?.reportPath ? (
                      <div style={{
                        width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
                        background: 'rgba(250,204,21,0.15)', border: '1px solid rgba(250,204,21,0.4)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 9, color: '#facc15', fontWeight: 900,
                      }} title="Entrega gerada aguardando confirmação">!</div>
                    ) : cExec?.dev?.task_id ? (
                      <div style={{
                        width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
                        background: 'rgba(56,189,248,0.15)', border: '1px solid rgba(56,189,248,0.4)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 9, color: '#38bdf8', fontWeight: 900,
                      }}>↻</div>
                    ) : null}
                  </div>

                  {/* Viability + bar */}
                  {cPP && (
                    <div style={{ marginTop: 10, paddingLeft: isActive ? 4 : 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{
                          fontSize: 9, fontWeight: 800, color: cPP.viability_color,
                          letterSpacing: 0.5,
                        }}>
                          {cPP.viability_icon} POTENCIAL {cPP.viability.toUpperCase()}
                        </span>
                        <span style={{ fontSize: 9, color: '#475569' }}>{cPP.score}/100</span>
                      </div>
                      <ViabilityBar score={cPP.score} color={cPP.viability_color} />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </aside>

        {/* ── MAIN CONTENT ──────────────────────────────────────────────────── */}
        <main style={{ flex: 1, minWidth: 0, overflowY: 'auto', background: '#07080f' }}>

          {/* Category banner */}
          <div style={{
            padding: '28px 36px 24px',
            background: `linear-gradient(135deg, ${cat.color}0d 0%, transparent 60%)`,
            borderBottom: `1px solid ${cat.color}18`,
            display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 20,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
              <div style={{
                width: 60, height: 60, borderRadius: 20, flexShrink: 0,
                background: `radial-gradient(circle at 30% 30%, ${cat.color}40, ${cat.color}12)`,
                border: `1px solid ${cat.color}45`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 28, boxShadow: `0 0 40px ${cat.color}20, 0 8px 24px rgba(0,0,0,0.4)`,
              }}>
                {cat.icon}
              </div>
              <div>
                <div style={{ fontSize: 10, color: cat.color, letterSpacing: 2.5, textTransform: 'uppercase', fontWeight: 700, marginBottom: 6 }}>
                  {isImplemented ? 'Insight implementado' : 'Insight de Evolução'}
                </div>
                <div style={{ fontSize: 26, fontWeight: 900, color: '#f1f5f9', letterSpacing: -0.5, lineHeight: 1.1 }}>
                  {cat.title}
                </div>
                <div style={{ marginTop: 6, fontSize: 13, color: '#64748b', lineHeight: 1.5, maxWidth: 500 }}>
                  {cat.description}
                </div>
                {isImplemented && currentImplementation && (
                  <div style={{
                    marginTop: 12,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    borderRadius: 999,
                    border: '1px solid rgba(34,197,94,0.35)',
                    background: 'rgba(34,197,94,0.12)',
                    color: '#22c55e',
                    padding: '7px 12px',
                    fontSize: 11,
                    fontWeight: 800,
                  }}>
                    ✓ Implementado via {currentImplementation.method ?? 'validação'} · {formatDate(currentImplementation.confirmed_at)}
                  </div>
                )}
              </div>
            </div>

            {/* Execute CTA */}
            <div style={{ flexShrink: 0 }}>
              <button
                type="button"
                onClick={() => handleExecute(cat)}
                disabled={isExec}
                style={{
                  padding: '14px 28px', borderRadius: 16, border: 'none',
                  background: isExec
                    ? 'rgba(139,92,246,0.2)'
                    : dispatched
                    ? 'linear-gradient(135deg,#1e3a5f,#1d4ed8)'
                    : 'linear-gradient(135deg,#4c1d95,#6d28d9,#7c3aed)',
                  color: '#fff', fontWeight: 800, fontSize: 13, letterSpacing: 0.4,
                  cursor: isExec ? 'default' : 'pointer',
                  boxShadow: isExec ? 'none' : dispatched ? '0 8px 32px rgba(29,78,216,0.4)' : '0 8px 32px rgba(109,40,217,0.45)',
                  transition: 'all 0.2s', whiteSpace: 'nowrap',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}
              >
                {isExec ? '⏳ Enviando...' : dispatched ? '↻ Re-executar Agentes' : '▶ Executar com Agentes IRIS'}
              </button>
              <button
                type="button"
                onClick={() => handlePromote(cat)}
                disabled={promoting === cat.category_id}
                style={{
                  padding: '14px 20px', borderRadius: 16,
                  border: `1px solid ${cat.color}34`,
                  background: `${cat.color}12`,
                  color: cat.color,
                  fontWeight: 800, fontSize: 13, letterSpacing: 0.4,
                  cursor: promoting === cat.category_id ? 'wait' : 'pointer',
                  transition: 'all 0.2s', whiteSpace: 'nowrap',
                }}
              >
                {promoting === cat.category_id ? 'Commitando...' : 'Promover + Commit'}
              </button>
              <button
                type="button"
                onClick={() => handleCreateApplication(cat)}
                disabled={creatingApp === cat.category_id}
                style={{
                  padding: '14px 20px', borderRadius: 16,
                  border: `1px solid rgba(34,197,94,0.36)`,
                  background: 'rgba(34,197,94,0.12)',
                  color: '#22c55e',
                  fontWeight: 800, fontSize: 13, letterSpacing: 0.4,
                  cursor: creatingApp === cat.category_id ? 'wait' : 'pointer',
                  transition: 'all 0.2s', whiteSpace: 'nowrap',
                }}
              >
                {creatingApp === cat.category_id ? 'Gerando app...' : 'Criar App + Commit'}
              </button>
              <button
                type="button"
                onClick={() => handleTestImplementation(cat)}
                disabled={!currentProduct || testingImplementation === cat.category_id}
                style={{
                  padding: '12px 18px', borderRadius: 8,
                  border: `1px solid rgba(56,189,248,0.36)`,
                  background: currentProduct ? 'rgba(56,189,248,0.12)' : 'rgba(100,116,139,0.1)',
                  color: currentProduct ? '#38bdf8' : '#64748b',
                  fontWeight: 800, fontSize: 12, letterSpacing: 0.4,
                  cursor: !currentProduct || testingImplementation === cat.category_id ? 'wait' : 'pointer',
                  transition: 'all 0.2s', whiteSpace: 'nowrap',
                  marginTop: 8,
                }}
              >
                {testingImplementation === cat.category_id ? 'Testando...' : 'Testar Implementação'}
              </button>
              {dispatched && !isExec && (
                <div style={{ marginTop: 8, fontSize: 10, color: '#60a5fa', textAlign: 'center' }}>
                  DEV · MKT em execução ↓
                </div>
              )}
              {promotionResult[cat.category_id] && (
                <div style={{ marginTop: 8, fontSize: 10, color: cat.color, textAlign: 'center', maxWidth: 360 }}>
                  {promotionResult[cat.category_id]}
                </div>
              )}
              {applicationResult[cat.category_id] && (
                <div style={{ marginTop: 8, fontSize: 10, color: '#22c55e', textAlign: 'center', maxWidth: 420 }}>
                  {applicationResult[cat.category_id]}
                </div>
              )}
              {testResult[cat.category_id] && (
                <div style={{ marginTop: 8, fontSize: 10, color: '#38bdf8', textAlign: 'center', maxWidth: 420 }}>
                  {testResult[cat.category_id]}
                </div>
              )}
              {isImplemented && currentImplementation?.success_criteria?.length ? (
                <div style={{ marginTop: 10, fontSize: 10, color: '#22c55e', textAlign: 'center', maxWidth: 420, lineHeight: 1.5 }}>
                  Confirmado: {currentImplementation.success_criteria.slice(0, 3).join(' · ')}
                </div>
              ) : null}
            </div>
          </div>

          {/* Scrollable content area */}
          <div style={{ padding: '28px 36px', display: 'flex', flexDirection: 'column', gap: 28 }}>

            {/* ── Product Factory Premium Status ──────────────────────────── */}
            <section>
              <div style={{ fontSize: 9, color: '#334155', letterSpacing: 2.5, textTransform: 'uppercase', fontWeight: 700, marginBottom: 14 }}>
                ◈ Product Factory · Gates Premium
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12 }}>
                <div style={{ borderRadius: 8, border: `1px solid ${cat.color}24`, background: `${cat.color}0b`, padding: 14 }}>
                  <div style={{ fontSize: 9, color: '#64748b', letterSpacing: 1.4, textTransform: 'uppercase', fontWeight: 800 }}>Produtos</div>
                  <div style={{ marginTop: 6, fontSize: 24, fontWeight: 900, color: '#f8fafc' }}>{factoryMetrics?.total_products ?? 0}</div>
                  <div style={{ marginTop: 4, fontSize: 10, color: '#64748b' }}>
                    Valor médio {Number(factoryMetrics?.average_value_score ?? 0).toFixed(1)}
                  </div>
                </div>

                <div style={{ borderRadius: 8, border: '1px solid rgba(34,197,94,0.24)', background: 'rgba(34,197,94,0.08)', padding: 14 }}>
                  <div style={{ fontSize: 9, color: '#64748b', letterSpacing: 1.4, textTransform: 'uppercase', fontWeight: 800 }}>Gate de Valor</div>
                  <div style={{ marginTop: 6, fontSize: 24, fontWeight: 900, color: '#22c55e' }}>
                    {formatPercent(factoryMetrics?.value_gate_pass_rate)}
                  </div>
                  <div style={{ marginTop: 4, fontSize: 10, color: '#64748b' }}>aprovados no padrão premium</div>
                </div>

                <div style={{ borderRadius: 8, border: '1px solid rgba(56,189,248,0.24)', background: 'rgba(56,189,248,0.08)', padding: 14 }}>
                  <div style={{ fontSize: 9, color: '#64748b', letterSpacing: 1.4, textTransform: 'uppercase', fontWeight: 800 }}>Push GitHub</div>
                  <div style={{ marginTop: 6, fontSize: 24, fontWeight: 900, color: '#38bdf8' }}>
                    {formatPercent(factoryMetrics?.github_push_rate)}
                  </div>
                  <div style={{ marginTop: 4, fontSize: 10, color: githubReady ? '#22c55e' : '#facc15' }}>
                    {githubReady ? 'repo dedicado pronto' : 'provisionamento pendente'}
                  </div>
                </div>

                <div style={{ borderRadius: 8, border: `1px solid ${githubReady ? 'rgba(34,197,94,0.28)' : 'rgba(250,204,21,0.28)'}`, background: githubReady ? 'rgba(34,197,94,0.08)' : 'rgba(250,204,21,0.08)', padding: 14 }}>
                  <div style={{ fontSize: 9, color: '#64748b', letterSpacing: 1.4, textTransform: 'uppercase', fontWeight: 800 }}>GitHub Runtime</div>
                  <div style={{ marginTop: 6, fontSize: 13, fontWeight: 900, color: githubReady ? '#22c55e' : '#facc15' }}>
                    {githubReady ? 'Pronto para standalone' : 'Atenção requerida'}
                  </div>
                  <div style={{ marginTop: 6, fontSize: 10, color: '#64748b', lineHeight: 1.5 }}>
                    {githubStatus?.gh_cli?.authenticated
                      ? `gh CLI: ${githubStatus.gh_cli.account || 'autenticado'}`
                      : githubStatus?.authenticated
                      ? `API: ${githubStatus.login || 'autenticada'}`
                      : 'sem autenticação confirmada'}
                  </div>
                </div>
              </div>

              {currentProduct && (
                <div style={{
                  marginTop: 12,
                  borderRadius: 8,
                  border: `1px solid ${currentProduct.product_value_gate?.approved ? 'rgba(34,197,94,0.28)' : 'rgba(250,204,21,0.28)'}`,
                  background: currentProduct.product_value_gate?.approved ? 'rgba(34,197,94,0.07)' : 'rgba(250,204,21,0.07)',
                  padding: '14px 16px',
                  display: 'grid',
                  gridTemplateColumns: 'minmax(0, 1fr) auto',
                  gap: 16,
                  alignItems: 'center',
                }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 11, fontWeight: 900, color: '#e2e8f0' }}>{currentProduct.application_name}</span>
                      <Badge color={currentProduct.repo_strategy === 'dedicated_repository' ? '#38bdf8' : '#a78bfa'}>
                        {currentProduct.repo_strategy === 'dedicated_repository' ? 'Repo dedicado' : 'Repo IRIS'}
                      </Badge>
                      <Badge color={currentProduct.product_value_gate?.approved ? '#22c55e' : '#facc15'}>
                        Value Gate {currentProduct.product_value_gate?.score ?? 0}/{currentProduct.product_value_gate?.threshold ?? 85}
                      </Badge>
                      <Badge color={currentProduct.pushed_to_github ? '#22c55e' : '#facc15'}>
                        {currentProduct.pushed_to_github ? 'Push confirmado' : 'Push pendente'}
                      </Badge>
                      {currentProduct.last_test_result && (
                        <Badge color={currentProduct.last_test_result.passed ? '#22c55e' : '#f87171'}>
                          {currentProduct.last_test_result.passed ? 'Teste aprovado' : 'Teste reprovado'}
                        </Badge>
                      )}
                    </div>
                    <div style={{ marginTop: 7, fontSize: 10, color: '#64748b', fontFamily: 'monospace', wordBreak: 'break-all' }}>
                      {currentProduct.application_slug} · commit {currentProduct.commit_sha || '—'} · {formatDate(currentProduct.created_at)}
                    </div>
                    {currentProduct.last_test_result ? (
                      <div style={{ marginTop: 7, fontSize: 10, color: currentProduct.last_test_result.passed ? '#22c55e' : '#f87171' }}>
                        Último teste: {currentProduct.last_test_result.test_kind} · {formatDate(currentProduct.last_test_result.tested_at)}
                      </div>
                    ) : null}
                    {currentProduct.product_value_gate?.failed_checks?.length ? (
                      <div style={{ marginTop: 7, fontSize: 10, color: '#facc15' }}>
                        Pendências: {currentProduct.product_value_gate.failed_checks.join(', ')}
                      </div>
                    ) : null}
                  </div>
                  {currentProduct.github_repo_url ? (
                    <a
                      href={currentProduct.github_repo_url}
                      target="_blank"
                      rel="noreferrer"
                      style={{
                        textDecoration: 'none',
                        color: '#f0f6ff',
                        border: '1px solid rgba(240,246,255,0.18)',
                        background: 'rgba(240,246,255,0.08)',
                        borderRadius: 8,
                        padding: '8px 12px',
                        fontSize: 11,
                        fontWeight: 800,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      Abrir GitHub ↗
                    </a>
                  ) : (
                    <div style={{ fontSize: 10, color: '#64748b', whiteSpace: 'nowrap' }}>sem URL remota</div>
                  )}
                </div>
              )}

              {githubStatus?.blockers?.length ? (
                <div style={{ marginTop: 10, fontSize: 11, color: '#f87171', lineHeight: 1.6 }}>
                  GitHub bloqueado: {githubStatus.blockers.map((item) => item.message).join(' · ')}
                </div>
              ) : githubStatus?.warnings?.length ? (
                <div style={{ marginTop: 10, fontSize: 11, color: '#facc15', lineHeight: 1.6 }}>
                  GitHub: {githubStatus.warnings[0].message}
                </div>
              ) : null}
            </section>

            {/* ── Log de Execução em Tempo Real ───────────────────────────── */}
            {exec && (
              <section>
                <div style={{ fontSize: 9, color: '#334155', letterSpacing: 2.5, textTransform: 'uppercase', fontWeight: 700, marginBottom: 14 }}>
                  ◈ Execução em Tempo Real · Agentes IRIS
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                  <LogPanel team="DEV" color="#38bdf8" task={exec.dev} catColor={cat.color} />
                  <LogPanel team="MARKETING" color="#a78bfa" task={exec.marketing} catColor={cat.color} />
                </div>
              </section>
            )}

            {/* ── Potencial Comercial ─────────────────────────────────────── */}
            {pp && (
              <section>
                <div style={{ fontSize: 9, color: '#334155', letterSpacing: 2.5, textTransform: 'uppercase', fontWeight: 700, marginBottom: 14 }}>
                  ◈ Potencial Comercial & Impacto Operacional
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>

                  <div style={{
                    borderRadius: 18, overflow: 'hidden',
                    border: `1px solid ${pp.viability_color}28`,
                    background: `linear-gradient(145deg, ${pp.viability_color}0e, rgba(6,8,14,0.97))`,
                  }}>
                    <div style={{ height: 4, background: `linear-gradient(90deg, ${pp.viability_color}, transparent)` }} />
                    <div style={{ padding: '18px 20px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                        <span style={{ fontSize: 10, fontWeight: 800, color: pp.viability_color, letterSpacing: 1.5, textTransform: 'uppercase' }}>
                          Viabilidade de Produto
                        </span>
                        <span style={{
                          borderRadius: 999, padding: '4px 14px',
                          background: `${pp.viability_color}20`, border: `1px solid ${pp.viability_color}45`,
                          fontSize: 12, fontWeight: 900, color: pp.viability_color, letterSpacing: 0.3,
                        }}>
                          {pp.viability_icon} {pp.viability.toUpperCase()}
                        </span>
                      </div>
                      <ViabilityBar score={pp.score} color={pp.viability_color} />
                      <div style={{ marginTop: 14, fontSize: 12.5, color: '#94a3b8', lineHeight: 1.75 }}>
                        {pp.pitch}
                      </div>
                    </div>
                  </div>

                  <div style={{
                    borderRadius: 18, overflow: 'hidden',
                    border: '1px solid rgba(34,197,94,0.2)',
                    background: 'linear-gradient(145deg, rgba(34,197,94,0.06), rgba(6,8,14,0.97))',
                  }}>
                    <div style={{ height: 4, background: 'linear-gradient(90deg, #22c55e, transparent)' }} />
                    <div style={{ padding: '18px 20px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                        <span style={{ fontSize: 18 }}>⚡</span>
                        <span style={{ fontSize: 10, fontWeight: 800, color: '#22c55e', letterSpacing: 1.5, textTransform: 'uppercase' }}>
                          Impacto em Velocidade / Qualidade
                        </span>
                      </div>
                      <div style={{ fontSize: 12.5, color: '#94a3b8', lineHeight: 1.75 }}>
                        {pp.speed_impact}
                      </div>
                    </div>
                  </div>

                </div>
              </section>
            )}

            {/* ── Diretriz ────────────────────────────────────────────────── */}
            <section>
              <div style={{ fontSize: 9, color: '#334155', letterSpacing: 2.5, textTransform: 'uppercase', fontWeight: 700, marginBottom: 14 }}>
                ◈ Diretriz de Integração
              </div>
              <div style={{
                padding: '18px 22px', borderRadius: 16,
                background: `linear-gradient(90deg, ${cat.color}0c 0%, transparent 100%)`,
                border: `1px solid ${cat.color}20`,
              }}>
                <div style={{ fontSize: 13, color: '#cbd5e1', lineHeight: 1.8 }}>
                  <span style={{ fontWeight: 800, color: cat.color }}>→ </span>
                  {cat.recommendation}
                </div>
              </div>
            </section>

            {/* ── Análise de Implementação ────────────────────────────────── */}
            {cat.summary && (
              <section>
                <div style={{ fontSize: 9, color: '#334155', letterSpacing: 2.5, textTransform: 'uppercase', fontWeight: 700, marginBottom: 14 }}>
                  ◈ Análise de Implementação
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                  {SUMMARY_KEYS.map(({ key, label, emoji }) => (
                    <div key={key} style={{ borderRadius: 16, overflow: 'hidden', border: `1px solid ${cat.color}1c`, background: `linear-gradient(145deg, ${cat.color}0a, rgba(6,8,14,0.95))` }}>
                      <div style={{ height: 3, background: `linear-gradient(90deg, ${cat.color}70, transparent)` }} />
                      <div style={{ padding: '16px 18px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                          <span style={{ fontSize: 16 }}>{emoji}</span>
                          <span style={{ fontSize: 9, fontWeight: 800, color: cat.color, letterSpacing: 1.5, textTransform: 'uppercase' }}>{label}</span>
                        </div>
                        <div style={{ fontSize: 12.5, color: '#94a3b8', lineHeight: 1.75 }}>{cat.summary![key]}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* ── Top Projetos ────────────────────────────────────────────── */}
            <section style={{ paddingBottom: 40 }}>
              <div style={{ fontSize: 9, color: '#334155', letterSpacing: 2.5, textTransform: 'uppercase', fontWeight: 700, marginBottom: 14 }}>
                ◈ Top Projetos Identificados
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {cat.top_projects.map((proj, idx) => (
                  <div key={proj.id} style={{
                    display: 'flex', alignItems: 'center', gap: 14,
                    padding: '14px 18px', borderRadius: 16,
                    background: idx === 0
                      ? `linear-gradient(90deg, ${cat.color}0e, rgba(6,8,14,0.95))`
                      : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${idx === 0 ? cat.color + '28' : 'rgba(255,255,255,0.05)'}`,
                  }}>
                    <div style={{
                      flexShrink: 0, width: 36, height: 36, borderRadius: 12,
                      background: idx === 0 ? `linear-gradient(135deg,${cat.color}45,${cat.color}18)` : 'rgba(255,255,255,0.05)',
                      border: `1px solid ${idx === 0 ? cat.color + '50' : 'rgba(255,255,255,0.07)'}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: idx === 0 ? 16 : 12, fontWeight: 900,
                      color: idx === 0 ? cat.color : '#475569',
                      boxShadow: idx === 0 ? `0 0 16px ${cat.color}20` : 'none',
                    }}>
                      {idx === 0 ? '★' : idx + 1}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: idx === 0 ? '#f1f5f9' : '#cbd5e1', wordBreak: 'break-word' }}>
                        {proj.title}
                      </div>
                      {proj.project_names.length > 0 && (
                        <div style={{ fontSize: 10, color: '#475569', marginTop: 3 }}>{proj.project_names.join(' + ')}</div>
                      )}
                      {(proj.iris_fit ?? []).length > 0 && (
                        <div style={{ marginTop: 6, display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                          {(proj.iris_fit ?? []).slice(0, 4).map((tag) => (
                            <span key={tag} style={{
                              borderRadius: 7, padding: '2px 8px',
                              background: `${cat.color}10`, border: `1px solid ${cat.color}1e`,
                              fontSize: 9, color: cat.color, fontWeight: 600,
                            }}>{tag}</span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{
                        borderRadius: 12, padding: '6px 12px',
                        background: `${gradeColor(proj.grade)}14`, border: `1px solid ${gradeColor(proj.grade)}30`,
                        fontSize: 13, fontWeight: 900, color: gradeColor(proj.grade),
                      }}>
                        {proj.grade}
                        <span style={{ fontWeight: 500, fontSize: 10, opacity: 0.65, marginLeft: 4 }}>{proj.score}pts</span>
                      </div>
                      {proj.url && (
                        <a
                          href={proj.url} target="_blank" rel="noopener noreferrer"
                          style={{
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            width: 32, height: 32, borderRadius: 10,
                            border: `1px solid ${SCOUT_COLOR}28`, background: `${SCOUT_COLOR}0c`,
                            color: SCOUT_COLOR, textDecoration: 'none', fontSize: 14,
                          }}
                        >→</a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>

          </div>
        </main>
      </div>
    </div>
  );
};

// ─── Main Component ────────────────────────────────────────────────────────────

const SOURCES = ['all', 'github', 'gitlab', 'huggingface', 'huggingface_space', 'combination'] as const;
const GRADES  = ['all', 'S', 'A', 'B', 'C', 'D'] as const;

const ResearchHub: React.FC<Props> = ({ apiUrl }) => {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [config, setConfig] = useState<ScheduleConfig | null>(null);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [gradeFilter, setGradeFilter] = useState<string>('all');
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [scrapeMsg, setScrapeMsg] = useState<string | null>(null);
  const [showInsights, setShowInsights] = useState(false);
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [loadingInsights, setLoadingInsights] = useState(false);

  const refreshInsights = useCallback(async () => {
    const resp = await fetch(`${apiUrl}/research/insights`);
    if (resp.ok) {
      setInsights(await resp.json());
    }
  }, [apiUrl]);

  const handleOpenInsights = useCallback(async () => {
    setShowInsights(true);
    if (!insights) setLoadingInsights(true);
    try {
      await refreshInsights();
    } finally {
      setLoadingInsights(false);
    }
  }, [insights, refreshInsights]);

  useEffect(() => {
    if (!showInsights) return;
    const id = window.setInterval(() => {
      refreshInsights().catch(() => undefined);
    }, 15000);
    return () => window.clearInterval(id);
  }, [refreshInsights, showInsights]);

  const loadData = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: '80' });
      if (sourceFilter !== 'all') params.set('source', sourceFilter);
      if (gradeFilter !== 'all') params.set('grade', gradeFilter);

      const [findingsResp, statsResp, configResp, statusResp] = await Promise.all([
        fetch(`${apiUrl}/research/findings?${params}`),
        fetch(`${apiUrl}/research/stats`),
        fetch(`${apiUrl}/research/schedule`),
        fetch(`${apiUrl}/research/scheduler/status`),
      ]);

      if (!findingsResp.ok) throw new Error(`Findings: ${findingsResp.status}`);

      const findingsData = await findingsResp.json() as FindingsResponse;
      setFindings(findingsData.items);
      setLastUpdated(findingsData.last_updated);

      if (statsResp.ok) setStats(await statsResp.json());
      if (configResp.ok) setConfig(await configResp.json());
      if (statusResp.ok) setSchedulerStatus(await statusResp.json());

      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar dados');
    } finally {
      setLoading(false);
    }
  }, [apiUrl, sourceFilter, gradeFilter]);

  useEffect(() => {
    loadData();
    const id = window.setInterval(loadData, 15000);
    return () => window.clearInterval(id);
  }, [loadData]);

  const handleScrapeNow = useCallback(async () => {
    setScraping(true);
    setScrapeMsg(null);
    try {
      const resp = await fetch(`${apiUrl}/research/scrape`, { method: 'POST' });
      const data = await resp.json();
      setScrapeMsg(data.message || data.status);
      setTimeout(loadData, 3000);
    } catch (e) {
      setScrapeMsg('Erro ao iniciar raspagem');
    } finally {
      setScraping(false);
    }
  }, [apiUrl, loadData]);


  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'minmax(300px, 360px) minmax(0, 1fr)',
      gap: 18,
      padding: 18,
      height: '100%',
      overflow: 'hidden',
      background: 'radial-gradient(circle at top right, rgba(56,189,248,0.06), transparent 32%), #03030a',
    }}>
      {/* LEFT — Config panel */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0, overflowY: 'auto' }}>
        <SchedulePanel
          apiUrl={apiUrl}
          config={config}
          status={schedulerStatus}
          scraping={scraping}
          onScrapeNow={handleScrapeNow}
          onRefresh={loadData}
        />
        {scrapeMsg && (
          <div style={{
            padding: '10px 14px', borderRadius: 12,
            border: `1px solid ${SCOUT_COLOR}33`, background: `${SCOUT_COLOR}0a`,
            fontSize: 12, color: SCOUT_COLOR, lineHeight: 1.5,
          }}>
            {scrapeMsg}
          </div>
        )}
      </div>

      {/* RIGHT — Findings */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0, overflow: 'hidden' }}>
        {/* Header */}
        <div style={{
          padding: 18, borderRadius: 18, border: `1px solid ${BORDER}`,
          background: 'linear-gradient(180deg, rgba(12,12,22,0.94), rgba(8,8,18,0.92))',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
            <div>
              <div style={{ fontSize: 11, color: SCOUT_COLOR, letterSpacing: 2, textTransform: 'uppercase' }}>
                Intel Hub
              </div>
              <div style={{ marginTop: 6, fontSize: 22, fontWeight: 800, color: '#f8fafc' }}>
                Projetos Promissores
              </div>
              {lastUpdated && (
                <div style={{ marginTop: 4, fontSize: 11, color: '#475569' }}>
                  Última atualização: {formatDate(lastUpdated)}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                onClick={handleOpenInsights}
                style={{
                  borderRadius: 12, border: `1px solid rgba(251,191,36,0.35)`,
                  background: 'rgba(251,191,36,0.08)', color: '#fbbf24',
                  padding: '10px 16px', cursor: 'pointer', fontSize: 12, fontWeight: 700,
                }}
              >
                ⚡ Insights
              </button>
              <button
                type="button"
                onClick={loadData}
                style={{
                  borderRadius: 12, border: `1px solid ${BORDER}`,
                  background: CARD_BG, color: '#cbd5e1',
                  padding: '10px 14px', cursor: 'pointer', fontSize: 12,
                }}
              >
                Atualizar
              </button>
            </div>
          </div>

          {/* Stats */}
          {stats && (
            <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(6, minmax(0, 1fr))', gap: 10 }}>
              <StatCard label="Total" value={stats.total} />
              <StatCard label="GitHub" value={stats.by_source.github ?? 0} color="#f0f6ff" />
              <StatCard label="GitLab" value={stats.by_source.gitlab ?? 0} color="#fc6d26" />
              <StatCard label="HuggingFace" value={(stats.by_source.huggingface ?? 0) + (stats.by_source.huggingface_space ?? 0)} color="#fbbf24" />
              <StatCard label="Combinações" value={stats.by_source.combination ?? 0} color="#a78bfa" />
              <StatCard label="Score médio" value={stats.avg_score} color={SCOUT_COLOR} />
            </div>
          )}
        </div>

        {/* Filters */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ fontSize: 11, color: '#475569', letterSpacing: 1 }}>Fonte:</div>
          {SOURCES.map((s) => (
            <button
              key={s}
              onClick={() => setSourceFilter(s)}
              style={{
                borderRadius: 999, border: `1px solid ${sourceFilter === s ? SCOUT_COLOR + '66' : BORDER}`,
                background: sourceFilter === s ? `${SCOUT_COLOR}12` : CARD_BG,
                color: sourceFilter === s ? SCOUT_COLOR : '#94a3b8',
                padding: '5px 12px', fontSize: 11, fontWeight: 600, cursor: 'pointer',
              }}
            >
              {sourceLabel(s === 'all' ? 'all' : s)}
              {s === 'all' ? '' : ''}
            </button>
          ))}
          <div style={{ fontSize: 11, color: '#475569', letterSpacing: 1, marginLeft: 8 }}>Grade:</div>
          {GRADES.map((g) => (
            <button
              key={g}
              onClick={() => setGradeFilter(g)}
              style={{
                borderRadius: 999, border: `1px solid ${gradeFilter === g ? gradeColor(g) + '66' : BORDER}`,
                background: gradeFilter === g ? `${gradeColor(g)}12` : CARD_BG,
                color: gradeFilter === g ? gradeColor(g) : '#94a3b8',
                padding: '5px 12px', fontSize: 11, fontWeight: 700, cursor: 'pointer',
              }}
            >
              {g}
            </button>
          ))}
        </div>

        {/* Findings list */}
        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', paddingRight: 4 }}>
          {error ? (
            <EmptyState msg={`Erro: ${error}`} color="#fca5a5" />
          ) : loading ? (
            <EmptyState msg="Carregando findings do SCOUT..." />
          ) : findings.length === 0 ? (
            <EmptyState msg="Nenhum finding encontrado. Clique em Raspar Agora para iniciar a primeira coleta." />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {findings.map((f) => (
                <FindingCard key={f.id} finding={f} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Insights — full-screen */}
      {showInsights && (
        loadingInsights ? (
          <div style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: '#06080e',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20,
          }}>
            <div style={{
              width: 56, height: 56, borderRadius: 20,
              background: 'radial-gradient(circle, rgba(56,189,248,0.2), rgba(56,189,248,0.05))',
              border: '1px solid rgba(56,189,248,0.3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26,
            }}>⚡</div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 800, color: '#e2e8f0', textAlign: 'center' }}>
                Gerando Intelligence Report...
              </div>
              <div style={{ fontSize: 12, color: '#334155', textAlign: 'center', marginTop: 6 }}>
                SCOUT-01 analisando projetos e potencial comercial
              </div>
            </div>
            <button
              type="button"
              onClick={() => setShowInsights(false)}
              style={{
                marginTop: 8, padding: '8px 18px', borderRadius: 10,
                border: '1px solid rgba(255,255,255,0.08)',
                background: 'rgba(255,255,255,0.04)', color: '#475569',
                fontSize: 12, cursor: 'pointer',
              }}
            >
              Cancelar
            </button>
          </div>
        ) : insights ? (
          <InsightsModal data={insights} apiUrl={apiUrl} onClose={() => setShowInsights(false)} />
        ) : null
      )}
    </div>
  );
};

const EmptyState: React.FC<{ msg: string; color?: string }> = ({ msg, color = '#475569' }) => (
  <div style={{
    height: 240, display: 'flex', alignItems: 'center', justifyContent: 'center',
    color, fontSize: 13, textAlign: 'center', lineHeight: 1.6, padding: 24,
  }}>
    {msg}
  </div>
);

export default ResearchHub;
