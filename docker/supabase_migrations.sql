-- =============================================================================
-- AI Office System — Supabase Migrations
-- Executar no Supabase Dashboard > SQL Editor ou via Supabase MCP.
--
-- Ordem de execução:
--   1. Tabelas (tasks, agent_events, agent_states)
--   2. Índices
--   3. Row Level Security
--   4. Policies
--   5. Realtime
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. TABELAS
-- -----------------------------------------------------------------------------

-- Tabela de tarefas
-- Mantém o estado durável de cada tarefa orquestrada pelo LangGraph.
CREATE TABLE IF NOT EXISTS tasks (
  task_id         UUID          PRIMARY KEY,
  team            TEXT          NOT NULL CHECK (team IN ('dev', 'marketing')),
  status          TEXT          NOT NULL DEFAULT 'queued'
                                CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  request         TEXT          NOT NULL,
  senior_directive TEXT,
  subtasks        JSONB         NOT NULL DEFAULT '[]',
  agent_outputs   JSONB         NOT NULL DEFAULT '{}',
  final_output    TEXT,
  error_count     INTEGER       NOT NULL DEFAULT 0,
  retry_count     INTEGER       NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  tasks IS 'Estado durável de cada tarefa do AI Office System.';
COMMENT ON COLUMN tasks.task_id          IS 'UUID v4 gerado pelo backend Python.';
COMMENT ON COLUMN tasks.team             IS 'Equipe responsável: dev ou marketing.';
COMMENT ON COLUMN tasks.status           IS 'Ciclo de vida: queued → running → completed | failed.';
COMMENT ON COLUMN tasks.senior_directive IS 'Diretriz gerada pelo Senior Agent (Claude Sonnet).';
COMMENT ON COLUMN tasks.subtasks         IS 'Array de subtarefas gerado pelo Planner Agent.';
COMMENT ON COLUMN tasks.agent_outputs    IS 'Mapa agent_id → resultado (texto).';
COMMENT ON COLUMN tasks.final_output     IS 'Output consolidado pelo Quality Gate.';


-- Tabela de eventos (log auditável)
-- Espelho durável do Redis Stream: cada OfficialEvent é persistido aqui.
CREATE TABLE IF NOT EXISTS agent_events (
  id          BIGSERIAL     PRIMARY KEY,
  event_id    UUID          NOT NULL,
  event_type  TEXT          NOT NULL,
  team        TEXT          NOT NULL,
  agent_id    TEXT          NOT NULL,
  agent_role  TEXT          NOT NULL,
  task_id     UUID          REFERENCES tasks(task_id) ON DELETE SET NULL,
  payload     JSONB         NOT NULL DEFAULT '{}',
  timestamp   TIMESTAMPTZ   NOT NULL
);

COMMENT ON TABLE  agent_events IS 'Log auditável de todos os eventos emitidos pelos agentes.';
COMMENT ON COLUMN agent_events.event_id   IS 'UUID único do evento (gerado no Python).';
COMMENT ON COLUMN agent_events.event_type IS 'Tipo do evento (ex.: AGENT_THINKING, TASK_COMPLETE).';
COMMENT ON COLUMN agent_events.payload    IS 'Dados arbitrários do evento (JSONB).';
COMMENT ON COLUMN agent_events.task_id    IS 'FK para tasks; NULL para eventos de sistema.';


-- Tabela de estado dos agentes
-- Snapshot em tempo real do status de cada agente.
CREATE TABLE IF NOT EXISTS agent_states (
  agent_id        TEXT          PRIMARY KEY,
  agent_role      TEXT          NOT NULL,
  team            TEXT          NOT NULL,
  status          TEXT          NOT NULL DEFAULT 'idle'
                                CHECK (status IN ('idle', 'thinking', 'working', 'moving', 'error')),
  current_task_id UUID          REFERENCES tasks(task_id) ON DELETE SET NULL,
  completed_tasks INTEGER       NOT NULL DEFAULT 0,
  error_count     INTEGER       NOT NULL DEFAULT 0,
  last_active     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  agent_states IS 'Estado instantâneo de cada agente para a visual engine.';
COMMENT ON COLUMN agent_states.agent_id   IS 'Identificador único do agente (ex.: dev_coder_1).';
COMMENT ON COLUMN agent_states.status     IS 'Status atual do agente para animações no frontend.';


-- -----------------------------------------------------------------------------
-- 2. ÍNDICES
-- -----------------------------------------------------------------------------

-- agent_events
CREATE INDEX IF NOT EXISTS idx_agent_events_task_id
    ON agent_events(task_id);

CREATE INDEX IF NOT EXISTS idx_agent_events_timestamp
    ON agent_events(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_agent_events_event_type
    ON agent_events(event_type);

-- tasks
CREATE INDEX IF NOT EXISTS idx_tasks_team
    ON tasks(team);

CREATE INDEX IF NOT EXISTS idx_tasks_status
    ON tasks(status);

CREATE INDEX IF NOT EXISTS idx_tasks_created_at
    ON tasks(created_at DESC);

-- agent_states
CREATE INDEX IF NOT EXISTS idx_agent_states_team
    ON agent_states(team);

CREATE INDEX IF NOT EXISTS idx_agent_states_status
    ON agent_states(status);


-- -----------------------------------------------------------------------------
-- 3. TRIGGER — atualização automática de updated_at em tasks
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'set_tasks_updated_at'
  ) THEN
    CREATE TRIGGER set_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
  END IF;
END $$;


-- -----------------------------------------------------------------------------
-- 4. ROW LEVEL SECURITY
-- -----------------------------------------------------------------------------

ALTER TABLE tasks         ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_events  ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_states  ENABLE ROW LEVEL SECURITY;


-- -----------------------------------------------------------------------------
-- 5. POLICIES
-- Utiliza a service_role key no backend → acesso total.
-- O anon key do frontend só lê (sem escrita direta).
-- -----------------------------------------------------------------------------

-- tasks
DROP POLICY IF EXISTS "service_role_all" ON tasks;
CREATE POLICY "service_role_all"
    ON tasks FOR ALL
    USING (true)
    WITH CHECK (true);

-- Leitura anônima (frontend pode consultar status de tarefas)
DROP POLICY IF EXISTS "anon_read_tasks" ON tasks;
CREATE POLICY "anon_read_tasks"
    ON tasks FOR SELECT
    TO anon
    USING (true);

-- agent_events
DROP POLICY IF EXISTS "service_role_all" ON agent_events;
CREATE POLICY "service_role_all"
    ON agent_events FOR ALL
    USING (true)
    WITH CHECK (true);

-- agent_states
DROP POLICY IF EXISTS "service_role_all" ON agent_states;
CREATE POLICY "service_role_all"
    ON agent_states FOR ALL
    USING (true)
    WITH CHECK (true);

-- Leitura anônima do estado dos agentes (visual engine no frontend)
DROP POLICY IF EXISTS "anon_read_agent_states" ON agent_states;
CREATE POLICY "anon_read_agent_states"
    ON agent_states FOR SELECT
    TO anon
    USING (true);


-- -----------------------------------------------------------------------------
-- 6. REALTIME
-- Habilita Realtime para tabelas que o frontend precisa observar.
-- -----------------------------------------------------------------------------

ALTER PUBLICATION supabase_realtime ADD TABLE tasks;
ALTER PUBLICATION supabase_realtime ADD TABLE agent_states;


-- =============================================================================
-- FIM DA MIGRATION
-- =============================================================================
