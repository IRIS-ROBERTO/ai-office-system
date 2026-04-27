# SCOUT Insight Promotion - Novos Plugins para Agentes

Generated at: 2026-04-27T14:13:16.244186+00:00

## Category

- ID: `novos_plugins`
- Total found: 115
- Total analyzed by SCOUT: 277
- Recommendation: Integrar 'edict' como ferramenta MCP dos agentes IRIS — 115 projetos com potencial de expansão de capacidades.

## Market Potential

- Score: 84
- Viability: alto
- Speed/quality impact: Capacidades novas disponíveis imediatamente para todos os agentes via MCP — sem refatoração de core, plug-and-play.

Marketplace de ferramentas AI — plugins pay-per-use para agentes autônomos. Modelo AppStore com 30% de comissão por transação ou assinatura de plugin premium. Efeito de rede: quanto mais plugins, mais valioso o ecossistema IRIS.

## Implementation Summary

### What It Is

São ferramentas e frameworks de agentes de IA — como edict, everything-claude-code, deer-flow — que podem ser integrados ao IRIS como novas capacidades via MCP (Model Context Protocol). Cada ferramenta vira um 'poder extra' que qualquer agente pode invocar.

### Why It Matters

Serve para expandir o que os agentes IRIS conseguem fazer além do que já fazem hoje: buscar dados em tempo real, executar código, chamar APIs externas, orquestrar sub-agentes, e resolver tarefas que atualmente precisam de intervenção humana.

### Where IRIS Uses It

No PicoClaw MCP Bridge (gateway central de ferramentas do IRIS). O agente Dev, o Marketing e o SCOUT passariam a ter acesso às ferramentas de 'edict' como funções nativas, chamadas diretamente durante a execução de tarefas.

### What We Build

Uma classe Tool wrapper para 'edict' registrada no backend IRIS. Com isso: qualquer agente pode invocar a ferramenta via `tool.run(input)`, o resultado aparece no log de execução, e a tarefa avança automaticamente — sem precisar de um humano para fazer essa etapa manual.

## Top Projects

1. [edict](https://github.com/cft0808/edict) - grade S / score 97 / source github
2. [everything-claude-code](https://github.com/affaan-m/everything-claude-code) - grade S / score 93 / source github
3. [deer-flow](https://github.com/bytedance/deer-flow) - grade S / score 90 / source github
4. [zeroclaw](https://github.com/zeroclaw-labs/zeroclaw) - grade S / score 90 / source github
5. [oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent) - grade S / score 87 / source github

## Delivery Contract

- Create a technical spike before production integration.
- Keep implementation inside the authorized IRIS workspace or AIteams project root.
- Commit every new artifact with `github_commit`.
- Return `DELIVERY_EVIDENCE` with validation and SHA.
- Block promotion if license, security, or dependency risk is unacceptable.
