# SCOUT Insight Promotion - Memória e RAG

Generated at: 2026-04-26T21:56:33.667118+00:00

## Category

- ID: `memoria_rag`
- Total found: 78
- Total analyzed by SCOUT: 274
- Recommendation: Implementar 'daily_stock_analysis' para memória persistente entre sessões dos agentes — 78 soluções de RAG encontradas.

## Market Potential

- Score: 90
- Viability: altíssimo
- Speed/quality impact: Agentes com memória persistente não repetem erros anteriores e reutilizam soluções validadas — aprendizado contínuo sem retrabalho.

Knowledge Base inteligente como SaaS — empresas pagam para ter documentos, histórico e processos acessíveis por agentes AI em tempo real. Recorrência mensal garantida. Upsell: analytics de uso + relatórios automáticos de inteligência organizacional.

## Implementation Summary

### What It Is

São sistemas de embeddings e recuperação semântica — como daily_stock_analysis, mempalace, WeKnora. Transformam textos em vetores numéricos para encontrar informações relevantes por similaridade de significado, não apenas por palavra-chave.

### Why It Matters

Serve para dar memória de longo prazo aos agentes IRIS: lembrar de projetos anteriores, decisões técnicas já tomadas, padrões de código do repositório, e contexto de tarefas passadas. Hoje os agentes 'esquecem tudo' a cada nova sessão — RAG resolve isso.

### Where IRIS Uses It

No memory-gateway e no Supabase (que já está configurado no IRIS). Antes de executar uma tarefa, o agente consultaria o RAG: 'já fizemos algo parecido antes?' — e reutilizaria soluções anteriores em vez de reinventar do zero.

### What We Build

Pipeline RAG com 'daily_stock_analysis': ao concluir cada tarefa, salvar o resumo + código gerado como vetores no Supabase. Ao iniciar nova tarefa, recuperar os 3 contextos mais similares e incluir no prompt do agente. Resultado prático: agentes que aprendem com o histórico do projeto.

## Top Projects

1. [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) - grade S / score 87 / source github
2. [mempalace](https://github.com/MemPalace/mempalace) - grade S / score 87 / source github
3. [WeKnora](https://github.com/Tencent/WeKnora) - grade S / score 86 / source github
4. [FastGPT](https://github.com/labring/FastGPT) - grade S / score 85 / source github
5. [haystack](https://github.com/deepset-ai/haystack) - grade S / score 85 / source github

## Delivery Contract

- Create a technical spike before production integration.
- Keep implementation inside the authorized IRIS workspace or AIteams project root.
- Commit every new artifact with `github_commit`.
- Return `DELIVERY_EVIDENCE` with validation and SHA.
- Block promotion if license, security, or dependency risk is unacceptable.
