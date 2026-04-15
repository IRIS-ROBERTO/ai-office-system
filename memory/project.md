---
name: AI Office System — Project Context
description: Projeto de escritório visual multiagente com dois times de IA (Dev + Marketing)
type: project
---

AI Office System em desenvolvimento ativo.

**Why:** Substituir times humanos completos com agentes IA de baixo custo, executando local via Ollama com Senior Agent (Sonnet) apenas para governança.

**How to apply:** Toda nova feature deve respeitar a arquitetura em camadas: EventBus → Orchestrator → Agents → Visual Engine. Nenhuma animação pode ser fictícia.

## Estado atual
- 54 arquivos criados, commit inicial feito (hash: 3284dad)
- Repositório local: `C:\Users\radar\Desktop\SUCESSOS!!!!!!!!!!!!!!!!!!!!!!!!!!\ESCRITORIO\ai-office-system`
- GitHub: pendente de autenticação para push
- GitHub username: IRIS-ROBERTO / iris369.iart@gmail.com

## Stack definida
- Backend: Python/FastAPI + LangGraph + CrewAI + Redis Streams + Supabase
- Frontend: React + PixiJS + Zustand + WebSocket  
- Modelos locais: Qwen2.5-Coder:32b, Llama3.3:70b, DeepSeek-R1:32b (via Ollama)
- Senior: Claude Sonnet 4.6 via OpenRouter
- Persistência: Supabase (PostgreSQL gerenciado)

## Próximos passos
1. GitHub auth (usuário precisa rodar `gh auth login` ou fornecer PAT)
2. Rodar migrations SQL no Supabase
3. Testar startup do backend
4. npm install + testar frontend

## Modelo operacional obrigatório
- O plano de governança dos agentes está em `docs/agent-operating-model.md`.
- Nenhuma tarefa versionável deve ser marcada como concluída sem evidência de commit.
- O quality gate deve exigir arquivos alterados, validação executada e SHA de commit.
- Projetos complexos não podem ser reduzidos a uma única subtarefa genérica.
- CROWN deve priorizar evidência operacional sobre resposta textual.
