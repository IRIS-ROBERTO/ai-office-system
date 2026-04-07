-- =============================================================================
-- AI Office System — Improvement Loop Migration
-- Executar APÓS supabase_migrations.sql (depende da tabela `tasks`).
--
-- Ordem de execução:
--   1. Tabelas (critical_analyses, improvement_proposals)
--   2. Índices
--   3. Row Level Security
--   4. Policies
--   5. Realtime
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. TABELAS
-- -----------------------------------------------------------------------------

-- Tabela de análises críticas
-- Cada agente escreve uma auto-análise ao concluir uma tarefa.
-- Alimenta o histórico de aprendizado do sistema ao longo do tempo.
CREATE TABLE IF NOT EXISTS critical_analyses (
    id                      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id                TEXT          NOT NULL,
    agent_role              TEXT          NOT NULL,
    task_id                 UUID          REFERENCES tasks(task_id) ON DELETE SET NULL,
    what_worked             TEXT,
    what_failed             TEXT,
    bottleneck              TEXT,
    improvement_suggestion  TEXT,
    confidence              FLOAT         CHECK (confidence >= 0.0 AND confidence <= 1.0),
    category                TEXT          CHECK (category IN ('performance', 'quality', 'architecture', 'tooling')),
    estimated_impact        TEXT          CHECK (estimated_impact IN ('low', 'medium', 'high')),
    created_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  critical_analyses IS 'Auto-análises produzidas pelos agentes ao concluir tarefas.';
COMMENT ON COLUMN critical_analyses.agent_id              IS 'Identificador único do agente que produziu a análise.';
COMMENT ON COLUMN critical_analyses.agent_role            IS 'Role do agente (ex.: backend, qa, planner).';
COMMENT ON COLUMN critical_analyses.task_id               IS 'FK para a tarefa analisada. NULL se tarefa deletada.';
COMMENT ON COLUMN critical_analyses.what_worked           IS 'O que funcionou bem — especificidade obrigatória.';
COMMENT ON COLUMN critical_analyses.what_failed           IS 'O que não funcionou — honestidade brutal obrigatória.';
COMMENT ON COLUMN critical_analyses.bottleneck            IS 'Onde o agente perdeu mais tempo ou tokens.';
COMMENT ON COLUMN critical_analyses.improvement_suggestion IS 'Proposta concreta e acionável de melhoria.';
COMMENT ON COLUMN critical_analyses.confidence            IS 'Confiança do agente na sugestão: 0.0 a 1.0.';
COMMENT ON COLUMN critical_analyses.category              IS 'Categoria: performance | quality | architecture | tooling.';
COMMENT ON COLUMN critical_analyses.estimated_impact      IS 'Impacto esperado da melhoria: low | medium | high.';


-- Tabela de propostas de melhoria
-- Agregação das análises críticas — cada proposal representa um padrão
-- identificado por um ou mais agentes, aguardando decisão do usuário.
CREATE TABLE IF NOT EXISTS improvement_proposals (
    proposal_id         UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    title               TEXT          NOT NULL,
    description         TEXT,
    category            TEXT          CHECK (category IN ('performance', 'quality', 'architecture', 'tooling')),
    estimated_impact    TEXT          CHECK (estimated_impact IN ('low', 'medium', 'high')),
    estimated_effort    TEXT          CHECK (estimated_effort IN ('1h', '1d', '1week')),
    supporting_agents   JSONB         NOT NULL DEFAULT '[]',
    status              TEXT          NOT NULL DEFAULT 'pending'
                                      CHECK (status IN ('pending', 'approved', 'rejected', 'implemented')),
    votes               INTEGER       NOT NULL DEFAULT 1 CHECK (votes >= 1),
    community_reference TEXT,
    user_comment        TEXT,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    decided_at          TIMESTAMPTZ
);

COMMENT ON TABLE  improvement_proposals IS 'Propostas de melhoria agregadas para aprovação do usuário.';
COMMENT ON COLUMN improvement_proposals.proposal_id        IS 'UUID v4 — gerado pelo backend Python.';
COMMENT ON COLUMN improvement_proposals.title              IS 'Título conciso da proposta (< 60 chars).';
COMMENT ON COLUMN improvement_proposals.description        IS 'Descrição técnica detalhada: o que mudar e por quê.';
COMMENT ON COLUMN improvement_proposals.category           IS 'Categoria: performance | quality | architecture | tooling.';
COMMENT ON COLUMN improvement_proposals.estimated_impact   IS 'Impacto esperado: low | medium | high.';
COMMENT ON COLUMN improvement_proposals.estimated_effort   IS 'Esforço estimado de implementação: 1h | 1d | 1week.';
COMMENT ON COLUMN improvement_proposals.supporting_agents  IS 'Array JSON com IDs dos agentes que identificaram o problema.';
COMMENT ON COLUMN improvement_proposals.status             IS 'Ciclo de vida: pending → approved | rejected → implemented.';
COMMENT ON COLUMN improvement_proposals.votes              IS 'Quantos agentes identificaram o mesmo problema (maior = mais urgente).';
COMMENT ON COLUMN improvement_proposals.community_reference IS 'Referência de best practice da comunidade (LangGraph, CrewAI, etc.).';
COMMENT ON COLUMN improvement_proposals.user_comment       IS 'Comentário do usuário ao aprovar ou rejeitar.';
COMMENT ON COLUMN improvement_proposals.decided_at         IS 'Timestamp da decisão do usuário (aprovação ou rejeição).';


-- -----------------------------------------------------------------------------
-- 2. ÍNDICES
-- -----------------------------------------------------------------------------

-- critical_analyses
CREATE INDEX IF NOT EXISTS idx_critical_analyses_agent_id
    ON critical_analyses(agent_id);

CREATE INDEX IF NOT EXISTS idx_critical_analyses_task_id
    ON critical_analyses(task_id);

CREATE INDEX IF NOT EXISTS idx_critical_analyses_category
    ON critical_analyses(category);

CREATE INDEX IF NOT EXISTS idx_critical_analyses_estimated_impact
    ON critical_analyses(estimated_impact);

CREATE INDEX IF NOT EXISTS idx_critical_analyses_created_at
    ON critical_analyses(created_at DESC);

-- improvement_proposals
CREATE INDEX IF NOT EXISTS idx_improvement_proposals_status
    ON improvement_proposals(status);

CREATE INDEX IF NOT EXISTS idx_improvement_proposals_category
    ON improvement_proposals(category);

CREATE INDEX IF NOT EXISTS idx_improvement_proposals_votes
    ON improvement_proposals(votes DESC);

CREATE INDEX IF NOT EXISTS idx_improvement_proposals_estimated_impact
    ON improvement_proposals(estimated_impact);

CREATE INDEX IF NOT EXISTS idx_improvement_proposals_created_at
    ON improvement_proposals(created_at DESC);


-- -----------------------------------------------------------------------------
-- 3. VIEW — Propostas com métricas agregadas
-- Facilita dashboards sem joins complexos no cliente.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE VIEW improvement_proposals_summary AS
SELECT
    ip.proposal_id,
    ip.title,
    ip.category,
    ip.estimated_impact,
    ip.estimated_effort,
    ip.status,
    ip.votes,
    ip.community_reference,
    ip.created_at,
    ip.decided_at,
    COUNT(ca.id) AS total_analyses_in_category
FROM improvement_proposals ip
LEFT JOIN critical_analyses ca
    ON ca.category = ip.category
GROUP BY
    ip.proposal_id,
    ip.title,
    ip.category,
    ip.estimated_impact,
    ip.estimated_effort,
    ip.status,
    ip.votes,
    ip.community_reference,
    ip.created_at,
    ip.decided_at
ORDER BY ip.votes DESC, ip.created_at DESC;

COMMENT ON VIEW improvement_proposals_summary IS
    'Proposals com contagem de análises na mesma categoria — útil para dashboards.';


-- -----------------------------------------------------------------------------
-- 4. FUNÇÃO RPC — Estatísticas do loop de melhoria
-- Retorna métricas agregadas sem varredura full-table no cliente.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION get_improvement_stats()
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'total_analyses',           COUNT(*)                                                    FROM critical_analyses,
        'total_proposals',          (SELECT COUNT(*) FROM improvement_proposals),
        'pending_proposals',        (SELECT COUNT(*) FROM improvement_proposals WHERE status = 'pending'),
        'approved_proposals',       (SELECT COUNT(*) FROM improvement_proposals WHERE status = 'approved'),
        'rejected_proposals',       (SELECT COUNT(*) FROM improvement_proposals WHERE status = 'rejected'),
        'implemented_proposals',    (SELECT COUNT(*) FROM improvement_proposals WHERE status = 'implemented'),
        'avg_confidence',           (SELECT ROUND(AVG(confidence)::NUMERIC, 3) FROM critical_analyses),
        'top_category',             (
                                        SELECT category
                                        FROM critical_analyses
                                        GROUP BY category
                                        ORDER BY COUNT(*) DESC
                                        LIMIT 1
                                    )
    ) INTO result;

    RETURN result;
END;
$$;

COMMENT ON FUNCTION get_improvement_stats() IS
    'Retorna métricas agregadas do loop de melhoria — use via RPC do Supabase.';


-- -----------------------------------------------------------------------------
-- 5. ROW LEVEL SECURITY
-- -----------------------------------------------------------------------------

ALTER TABLE critical_analyses      ENABLE ROW LEVEL SECURITY;
ALTER TABLE improvement_proposals  ENABLE ROW LEVEL SECURITY;


-- -----------------------------------------------------------------------------
-- 6. POLICIES
-- service_role key (backend) → acesso total.
-- anon key (frontend) → apenas leitura.
-- -----------------------------------------------------------------------------

-- critical_analyses: acesso total para service_role
DROP POLICY IF EXISTS "service_role_all" ON critical_analyses;
CREATE POLICY "service_role_all"
    ON critical_analyses FOR ALL
    USING (true)
    WITH CHECK (true);

-- critical_analyses: leitura anônima (dashboards)
DROP POLICY IF EXISTS "anon_read_critical_analyses" ON critical_analyses;
CREATE POLICY "anon_read_critical_analyses"
    ON critical_analyses FOR SELECT
    TO anon
    USING (true);

-- improvement_proposals: acesso total para service_role
DROP POLICY IF EXISTS "service_role_all" ON improvement_proposals;
CREATE POLICY "service_role_all"
    ON improvement_proposals FOR ALL
    USING (true)
    WITH CHECK (true);

-- improvement_proposals: leitura anônima (frontend mostra proposals ao usuário)
DROP POLICY IF EXISTS "anon_read_improvement_proposals" ON improvement_proposals;
CREATE POLICY "anon_read_improvement_proposals"
    ON improvement_proposals FOR SELECT
    TO anon
    USING (true);


-- -----------------------------------------------------------------------------
-- 7. REALTIME
-- O frontend observa proposals em tempo real para atualizar o painel
-- de aprovação sem polling.
-- -----------------------------------------------------------------------------

ALTER PUBLICATION supabase_realtime ADD TABLE improvement_proposals;


-- =============================================================================
-- FIM DA MIGRATION — Improvement Loop
-- =============================================================================
