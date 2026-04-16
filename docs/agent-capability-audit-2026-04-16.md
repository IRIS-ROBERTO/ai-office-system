# IRIS Agent Capability Audit - 2026-04-16

## Scope

Audit autonomy, segmentation, memory, plugins, skills and MCP readiness for the IRIS agent team.

## Current Findings

- All canonical agents now have a documented capability profile exposed through `/agents/capabilities/matrix`.
- PicoClaw remains the production MCP bridge because it is installed, online and already governed by role policy.
- Dev gaps corrected in this audit: PIXEL, SHERLOCK and AEGIS now receive `picoclaw_mcp` directly instead of relying only on local tools.
- CrewAI `memory=False` remains intentional. Long-term memory should be handled by governed memory services to avoid uncontrolled context bloat and accidental secret retention.
- High-risk external writes remain centralized: GitHub remote writes, n8n executions and external automations stay under orchestrator/governance control.

## Hermes Agent Assessment

Repository checked: https://github.com/NousResearch/hermes-agent

Observed on 2026-04-16 through GitHub API:

- Stars: 92k+
- Language: Python
- Description: "The agent that grows with you"
- Recent activity: pushed on 2026-04-16
- Strengths: persistent memory, autonomous skill creation, cross-session recall, subagents, messaging gateways and multiple terminal backends.
- Risk: native Windows support is still open in upstream issues; official install path targets Linux, macOS, WSL2 and Termux.

Decision: do not replace PicoClaw directly. Build a runtime adapter first and evaluate Hermes in WSL2/sandbox as an optional backend.

## Memory Upgrade Candidates

- Hermes Agent: strong autonomous learning loop and skills, but should be evaluated as experimental runtime before production.
- MemOS: strong fit for IRIS memory layer because it advertises local SQLite, hybrid FTS/vector search, skill evolution and multi-agent collaboration.
- mem0: mature universal memory layer candidate for agent recall if we want a narrower memory service.

## Recommended Architecture

1. Keep PicoClaw as production MCP gateway.
2. Add `AgentRuntimeGateway` abstraction with providers: `picoclaw`, `hermes`, `memos`.
3. Integrate a governed memory layer before enabling self-improving behavior.
4. Add memory classes: project memory, agent skill memory, failure memory, decision memory and user preference memory.
5. Add safety gates: no secrets in memory, TTL by class, review/delete support and source attribution for recalled memory.
6. Add browser automation to QA behind policy, not direct ungoverned access.
7. Add SAST/dependency audit to AEGIS.
8. Add knowledge graph/search over `AIteams` projects for reuse across deliveries.

## External References

- Hermes Agent: https://github.com/NousResearch/hermes-agent
- Hermes features: https://hermes-agent.nousresearch.com/docs/user-guide/features/overview
- MemOS: https://github.com/MemTensor/MemOS
- mem0: https://github.com/mem0ai/mem0
- LangGraph: https://github.com/langchain-ai/langgraph
- AutoGen: https://github.com/microsoft/autogen
- CrewAI: https://github.com/crewAIInc/crewAI
- browser-use: https://github.com/browser-use/browser-use
- DeerFlow: https://github.com/bytedance/deer-flow
