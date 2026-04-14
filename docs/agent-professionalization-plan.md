# IRIS Agent Professionalization Plan

Objetivo: transformar o AI Office em uma plataforma de agentes profissionais, auditaveis e capazes de entregar qualquer input com padrao ouro: planejamento, execucao, validacao, commit, push, apresentacao e feedback humano.

## Diagnostico atual

- O sistema ja possui orquestrador, agentes Dev/Marketing, ferramentas de workspace, commit, GitHub token, Redis e logs.
- Os agentes ainda falham em entregas reais porque a execucao depende demais de um loop LLM+tools sem trilho deterministico.
- O gate ja reprova corretamente entregas sem DELIVERY_EVIDENCE, mas ainda precisa impedir loops longos por configuracao e forcar progresso etapa a etapa.
- O roteamento de modelo estava local-first, saturando Ollama e tornando tarefas de codigo lentas. A nova politica deve ser cloud-free-first para cerebro critico e local fallback.

## Arquitetura alvo

### 1. Brain Router

Responsabilidade: escolher o melhor cerebro por papel do agente sem custo.

Politica:
- Prioridade 1: OpenRouter free, somente modelos gratuitos confirmados no catalogo `/api/v1/models`.
- Prioridade 2: `openrouter/free` quando o papel precisar de tool calling/structured output e nao houver modelo especifico disponivel.
- Prioridade 3: Ollama local por papel, como fallback offline ou quando OpenRouter falhar.
- Nunca usar modelo pago automaticamente nesta fase.
- Toda escolha deve ser auditavel em `/health` e `/models/brain-router`.

Perfis iniciais:
- Orchestrator: planejamento, decomposicao, quality gate e decisoes.
- Planner: arquitetura, criterios de aceite, divisao de trabalho.
- Frontend: UI, CSS, JS/TS, acessibilidade e build.
- Backend: APIs, automacao, filesystem, validacao e contratos.
- QA: testes, build gates, regressao e evidencias.
- Security: OWASP, secrets, permissao e hardening.
- Docs: README, runbooks, handoff e changelog.
- Marketing Research/Strategy/Content/SEO/Social/Analytics: pesquisa, estrategia, conteudo, distribuicao e mensuracao.

### 2. Delivery Runner deterministico

Responsabilidade: transformar output dos agentes em entrega real.

Contrato obrigatorio:
- `PLAN_LOCK`: escopo, caminhos, arquivos e criterios.
- `WRITE_STAGE`: alteracoes via `workspace_file`.
- `VALIDATE_STAGE`: comando real, saida e exit code.
- `COMMIT_STAGE`: `github_commit` com SHA real.
- `PUSH_STAGE`: push confirmado ou falha declarada.
- `RUN_STAGE`: app/API executada em porta livre.
- `VERIFY_STAGE`: teste HTTP/browser ou comando objetivo.
- `HUMAN_APPROVAL_STAGE`: solicitar aprovacao para executar/verificar/apresentar.

Regra: o orquestrador nao pode marcar entrega como concluida se qualquer stage obrigatorio falhar.

### 3. PicoClaw Capability Governance

Responsabilidade: manter PicoClaw como gateway de plugins, MCPs e skills sem dar poder irrestrito aos agentes.

Contrato:
- O orquestrador controla a matriz de permissao por papel.
- Agentes podem usar apenas servidores MCP autorizados para sua funcao.
- Operacoes externas de alto risco, como push remoto, envio, merge, disparo de workflow e automacao externa, ficam concentradas no orquestrador.
- Ferramentas de escrita local continuam passando por workspace, validacao e commit auditavel.
- O operador deve conseguir auditar capacidades em `/tool-governance`, `/integrations/picoclaw` e `/agents/{agent_id}/capabilities`.

Politica inicial:
- Planner: filesystem, memory, sequential-thinking, brave-search, github read.
- Backend: filesystem, memory, supabase controlado, github read.
- Docs: filesystem, memory, notion controlado, github read.
- Research/Strategy/SEO/Analytics: pesquisa, memoria e dados conforme papel.
- Social/Content: memoria, Notion conforme politica e n8n apenas via orquestrador para efeitos externos.

### 4. Professional Agent Profiles

Cada agente deve ter:
- missao objetiva;
- escopo de autoridade;
- ferramentas permitidas;
- padrao de commit;
- checklists de qualidade;
- criterios de escalacao;
- limites de tempo e tentativa;
- politicas de modelo por atividade.

Exemplo:
- Frontend so finaliza se build passar, UI tiver estados visiveis e README explicar execucao.
- Backend so finaliza se contrato/API/script executar localmente com exit code 0.
- QA nao corrige silenciosamente: aponta falha, reproduz, valida correcao e registra evidencia.
- Security bloqueia entrega com secrets, path traversal, shell injection ou permissao perigosa.

### 5. Squad simultaneo controlado

Objetivo: trabalhar no mesmo projeto com paralelismo sem conflitos.

Regras:
- Cada subtask recebe ownership de arquivos.
- Branch/worktree por entrega.
- Commits pequenos por etapa.
- Merge interno apenas depois de build e status limpo.
- Conflito ou mudanca fora de ownership vira bloqueio, nao improviso.

### 6. Feedback loop real

Depois de cada entrega:
- registrar o que funcionou;
- registrar falhas por agente;
- classificar causa: modelo, prompt, ferramenta, validacao, repo, ambiente;
- atualizar perfil operacional do agente;
- gerar proposta de melhoria para o orquestrador.

## Fases de implementacao

### Fase 1 - Cerebro e roteamento

- Criar Brain Router com OpenRouter free + fallback Ollama.
- Expor status em `/health`.
- Integrar agentes ao Brain Router.
- Registrar selecoes recentes de modelo.
- Bloquear pagos automaticos.

Status: concluido na primeira versao.

### Fase 2 - Execucao deterministica

- Criar `delivery_runner`.
- Fazer o orquestrador executar stages obrigatorios.
- Encerrar tarefas sem progresso antes de loops longos.
- Separar "agente sugeriu" de "plataforma validou".

Status: concluido na primeira versao.

Implementado:
- Manifesto por subtarefa em `.runtime/delivery-manifests/<task_id>/<subtask_id>.json`.
- Consulta API em `/tasks/{task_id}/delivery-manifests`.
- Stages obrigatorios: `PLAN_LOCK`, `AGENT_OUTPUT`, `EVIDENCE_PARSE`, `VALIDATION_VERIFY`, `COMMIT_VERIFY`.
- Feedback deterministico retornado ao agente na tentativa seguinte.
- Bloqueio objetivo quando nao houver `DELIVERY_EVIDENCE`, validacao ou commit verificavel.

### Fase 3 - PicoClaw e governanca de ferramentas

- Criar matriz central de capacidades por papel.
- Contextualizar `PicoClawMCPTool` por agente.
- Bloquear MCP desconhecido ou escrita externa fora do papel.
- Expor status e capacidades via API.

Status: concluido na primeira versao.

### Fase 4 - Professional profiles

- Criar arquivos de perfil para cada agente.
- Aplicar perfis nos prompts e no painel de configuracao.
- Permitir edicao controlada via UI/API.
- Versionar mudancas de personalidade operacional.

Status: pendente.

### Fase 5 - GitOps e apresentacao

- Padronizar worktree/branch por entrega.
- Exigir commits por etapa.
- Push confirmado para GitHub.
- Executar app em porta livre.
- Gerar link local e solicitar aprovacao humana.

Status: parcialmente existente, precisa hardening.

### Fase 6 - Avaliacao continua

- Score por agente: sucesso, tempo, falhas, retries, qualidade de evidencia.
- Dashboard de confiabilidade por papel.
- Auto-ajuste de modelo por agente com base em taxa de sucesso.
- Relatorio de melhoria por sprint.

Status: pendente.

## Criterios de pronto da plataforma

- Uma tarefa de projeto novo deve gerar arquivos reais, build, commit, push e app executando localmente.
- O usuario deve ver onde esta a tarefa, qual agente falhou e qual evidencia existe.
- Nenhuma tarefa pode ficar rodando por mais do que o SLA configurado.
- Nenhum agente pode alegar commit, teste ou push sem evidencia verificavel.
- O orquestrador deve escolher modelos gratuitos disponiveis e cair para local sem travar a entrega.
