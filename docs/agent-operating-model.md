# IRIS AI Office System — Modelo Operacional dos Agentes

Este documento estrutura os ajustes necessários para transformar o IRIS de um escritório visual de agentes em uma linha de produção auditável, versionada e confiável.

## 1. Diagnóstico Crítico

O sistema já tem uma boa fundação:

- Frontend visual com escritório, agentes, zonas, WebSocket e estado global.
- Backend com FastAPI, orquestradores, agentes, EventBus, health check e endpoints de tarefas.
- Agentes com papéis claros: CROWN, ATLAS, PIXEL, FORGE, SHERLOCK, AEGIS, LORE e marketing.
- Ferramentas para pesquisa, execução de código, GitHub, Notion, Supabase, n8n e PicoClaw.

O problema central é operacional:

- O sistema aceitava entregas sem evidência real.
- A tarefa podia ser marcada como concluída mesmo sem código implementado.
- A tool antiga de GitHub não fazia commit local real.
- O quality gate dependia demais de julgamento por LLM.
- O estado operacional ainda é muito in-memory.
- A UI mostrava atividade, mas nem sempre provava execução.

## 2. Princípios Não Negociáveis

1. Nenhuma tarefa versionável é concluída sem commit.
2. Nenhuma tarefa crítica é concluída sem teste ou validação objetiva.
3. Nenhuma entrega é aprovada sem evidência rastreável.
4. Nenhum agente deve alterar arquivos fora do escopo atribuído.
5. Nenhum segredo deve aparecer em logs, prompts, commits ou UI.
6. Nenhuma animação visual pode representar uma ação que não ocorreu no runtime.
7. Nenhum projeto grande pode ser reduzido a uma única subtarefa genérica.

## 3. Definition of Done Obrigatório

Toda subtarefa deve terminar com um bloco de evidência:

```text
DELIVERY_EVIDENCE
agent: <codename>
task_id: <uuid>
subtask_id: <uuid>
files_changed:
- <path>
validation:
- command: <command>
  result: passed|failed|not_applicable
commit:
  message: <message>
  sha: <short_sha>
  pushed: true|false
risks:
- <risk or none>
next_handoff: <agent or none>
```

Se esse bloco não existir, o quality gate deve reprovar automaticamente.

## 4. Workflow de Entrega

### 4.1 Intake

Toda demanda entra como `service_request` com:

- título
- time destino
- prioridade
- SLA
- critérios de aceite
- solicitante
- contexto completo

### 4.2 Planejamento

CROWN deve impedir subtarefas vagas.

Projetos complexos devem ser quebrados no mínimo em:

- ATLAS: arquitetura e plano
- FORGE: backend/API/eventos/persistência
- PIXEL: frontend/UI/estado/WebSocket
- SHERLOCK: testes e validação
- AEGIS: segurança e riscos
- LORE: documentação e runbook

### 4.3 Execução

Cada agente executa apenas seu escopo.

O output deve conter:

- o que foi alterado
- por que foi alterado
- como foi validado
- commit produzido
- pendências ou handoff

### 4.4 Quality Gate

O quality gate deve combinar:

- validações determinísticas
- leitura do output
- diff/commit real
- critérios de aceite
- logs de execução

LLM não pode ser a única fonte de aprovação.

### 4.5 Encerramento

CROWN só encerra a tarefa quando:

- todas as subtarefas obrigatórias passaram
- não há falhas críticas
- todos os commits existem
- build/test passaram quando aplicável
- documentação mínima foi atualizada

## 5. Git e Versionamento

### 5.1 Regra de Branch

Cada tarefa deve usar uma branch:

```text
task/<task_id_curto>-<slug>
```

Exemplo:

```text
task/9f38b0f5-office-operational-ui
```

### 5.2 Regra de Commit

Cada agente deve fazer commits pequenos e rastreáveis:

```text
<agent>: <ação objetiva>
```

Exemplos:

```text
PIXEL: add operational control tower
FORGE: persist execution evidence
SHERLOCK: add delivery validation checks
AEGIS: document secret rotation policy
```

### 5.3 Eventos Git Obrigatórios

O backend deve emitir:

- `git_commit`
- `git_push`
- `repo_created`
- `branch_created`
- `commit_failed`

Cada evento deve carregar:

- agent_id
- task_id
- subtask_id
- branch
- sha
- files
- pushed
- error, se houver

## 6. Quality Gates Determinísticos

Implementar validadores antes da aprovação por CROWN:

### 6.1 Git Gate

Reprova se:

- não houve commit em subtarefa versionável
- commit não inclui arquivos esperados
- branch está diferente da branch da tarefa
- push falhou e a tarefa exige push

### 6.2 Build Gate

Para frontend:

```text
cd frontend
npm run build
```

Para backend:

```text
.venv\Scripts\python.exe -m compileall backend
```

### 6.3 Test Gate

Quando houver testes:

```text
pytest
npm test
```

Se não houver testes, o agente deve justificar `not_applicable` e SHERLOCK deve validar a justificativa.

### 6.4 Security Gate

AEGIS deve verificar:

- vazamento de `.env`
- tokens em diff
- comandos destrutivos
- permissões excessivas
- endpoints sem validação

## 7. Persistência Operacional

Mover gradualmente de memória para Supabase/Postgres.

Redis real é obrigatório para operação premium. `fakeredis` só pode ser usado em desenvolvimento local e deve aparecer no `/health` como `redis=degraded_fake` e `event_bus_persistent=false`.

Tabelas necessárias:

### 7.1 tasks

- task_id
- request_id
- team
- status
- priority
- sla_seconds
- created_at
- updated_at
- current_agent_id
- branch

### 7.2 subtasks

- subtask_id
- task_id
- assigned_agent_id
- title
- description
- acceptance_criteria
- status
- started_at
- completed_at

### 7.3 execution_logs

- log_id
- task_id
- subtask_id
- agent_id
- stage
- message
- level
- metadata
- timestamp

### 7.4 delivery_evidence

- evidence_id
- task_id
- subtask_id
- agent_id
- files_changed
- validation_results
- commit_sha
- commit_message
- pushed
- risks
- created_at

### 7.5 git_events

- event_id
- task_id
- subtask_id
- agent_id
- branch
- sha
- files
- pushed
- error
- timestamp

### 7.6 handoffs

- handoff_id
- from_agent_id
- to_agent_id
- from_team
- to_team
- context
- deliverable_needed
- status
- created_at
- resolved_at

### 7.7 EventBus

- `REDIS_URL` aponta para Redis real.
- `EVENTBUS_ALLOW_FAKE_REDIS=true` só é aceitável em desenvolvimento local.
- `EVENTBUS_ALLOW_FAKE_REDIS=false` deve ser usado em staging/produção.
- `/health` deve expor `event_bus` e `event_bus_persistent`.
- Nenhum monitoramento pode tratar `fakeredis` como operação saudável.

## 8. Interface Operacional

A UI deve provar o que aconteceu.

### 8.1 Control Tower

Mostrar:

- queue
- running
- validation
- blocked
- done
- failed
- commits pendentes
- falhas de teste
- SLA estourado

### 8.2 Agent Details

Mostrar:

- tarefa atual
- arquivos sob responsabilidade
- últimos commits
- logs
- input/output
- dependências
- riscos

### 8.3 Task Inspector

Mostrar:

- pipeline completo
- agentes envolvidos
- critérios de aceite
- validações
- commits
- gargalos
- handoffs

### 8.4 Event Stream

Eventos críticos devem aparecer em tempo real:

- task_created
- task_started
- task_completed
- task_failed
- agent_status_changed
- git_commit
- git_push
- quality_gate_failed
- handoff_created

## 9. Segurança

### 9.1 Rotação de Segredos

Credenciais que apareceram em `.env` devem ser rotacionadas:

- GitHub token
- OpenRouter keys
- Gemini key
- Supabase secret key
- n8n bearer/API tokens

### 9.2 Política de Segredos

- `.env` nunca pode ser commitado.
- Logs nunca podem imprimir tokens.
- Prompts não devem incluir segredos.
- UI nunca deve exibir segredos.
- AEGIS deve bloquear commits com padrões de segredo.

### 9.3 Secret Scanning Local

Adicionar uma etapa antes do commit:

```text
git diff --cached
```

com detecção para:

- `ghp_`
- `sk-`
- `AIza`
- `sb_secret`
- `Bearer `

## 10. Handoffs e Squads

### 10.1 Handoff

Todo handoff deve conter:

- por que existe
- qual agente recebe
- o que precisa entregar
- quais arquivos/contextos estão envolvidos
- prazo/SLA

### 10.2 Squad Temporário

CROWN pode criar squads quando:

- há gargalo
- SLA em risco
- dependência entre times
- falha repetida no quality gate

Squad mínimo para feature dev:

- ATLAS
- FORGE ou PIXEL
- SHERLOCK
- AEGIS se houver risco

## 11. Roadmap de Implementação

### Fase 1 — Disciplina de entrega

Objetivo: impedir falsa conclusão.

- [x] Corrigir `github_commit` para commit local real.
- [x] Exigir evidência de commit no prompt da subtarefa.
- [x] Fazer quality gate reprovar output sem evidência de commit.
- [x] Criar parser de `DELIVERY_EVIDENCE`.
- [x] Salvar evidência no estado da tarefa.
- [x] Emitir eventos `git_commit` e `git_push`.
- [x] Expor EventBus degradado quando Redis real não estiver disponível.

### Fase 2 — Gates determinísticos

Objetivo: trocar confiança por verificação.

- [ ] Implementar `GitGate`.
- [ ] Implementar `BuildGate`.
- [ ] Implementar `TestGate`.
- [ ] Implementar `SecretGate`.
- [ ] Fazer CROWN só aprovar se todos os gates obrigatórios passarem.

### Fase 3 — Persistência

Objetivo: sobreviver a restart e auditar histórico.

- [ ] Criar migrations para `tasks`, `subtasks`, `execution_logs`, `delivery_evidence`, `git_events`, `handoffs`.
- [ ] Persistir eventos no Supabase.
- [ ] Reidratar fila no startup.
- [ ] Remover dependência de estado in-memory para status crítico.

### Fase 4 — UI operacional

Objetivo: mostrar operação real, não teatro visual.

- [ ] Mostrar commits por tarefa.
- [ ] Mostrar validações por tarefa.
- [ ] Mostrar gates aprovados/reprovados.
- [ ] Mostrar handoffs.
- [ ] Mostrar squads temporários.
- [ ] Mostrar SLA e gargalos com base em dados persistidos.

### Fase 5 — Governança

Objetivo: tornar o time previsível.

- [ ] Branch automática por tarefa.
- [ ] PR automático ao final da tarefa.
- [ ] Review obrigatório por SHERLOCK e AEGIS.
- [ ] Runbook de recuperação de falhas.
- [ ] Dashboard de produtividade por agente.

## 12. Métricas de Qualidade do Time

Medir por agente:

- tarefas concluídas
- taxa de reprovação no quality gate
- tempo médio por subtarefa
- commits por tarefa
- falhas de teste
- retrabalho
- handoffs criados
- handoffs resolvidos
- incidentes de segurança

Medir por sistema:

- lead time total
- SLA breach rate
- build pass rate
- test pass rate
- commit coverage
- task recovery após restart
- percentual de entregas com evidência completa

## 13. Próxima Ação Recomendada

Implementar a Fase 1 por completo:

1. Criar `DeliveryEvidence` no backend.
2. Parsear evidência do output do agente.
3. Salvar evidência no estado da tarefa.
4. Emitir `git_commit` quando `github_commit` funcionar.
5. Reprovar automaticamente quando a evidência estiver ausente.

Isso fecha o buraco mais perigoso: tarefa marcada como concluída sem entrega real.
