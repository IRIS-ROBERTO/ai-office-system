# IRIS Memory Gateway Policy

## Purpose

The Memory Gateway is the governed memory layer for IRIS agents. It captures only sanitized, auditable records and keeps PicoClaw, Hermes and MemOS integration paths separated from memory policy.

## Memory Classes

- `project_memory`: project decisions, approved commits and delivery structure.
- `agent_skill_memory`: reusable specialist patterns validated by delivery gates.
- `failure_memory`: blocked delivery causes and prevention notes.
- `decision_memory`: operator or orchestrator decisions.
- `user_preference_memory`: user preferences and office standards.
- `tool_memory`: tool usage patterns, validation commands and commit practices.

## Governance Rules

- No memory may contain API keys, GitHub tokens, private keys, passwords or `.env` values.
- Agent-generated memory requires orchestrator approval.
- Automatic memory capture is triggered only from approved `DeliveryRunner` manifests.
- Memory is append-only in the local provider to preserve auditability.
- External providers such as MemOS or Hermes must pass through the same policy before activation.
- MemOS is optional and non-blocking by default. The local JSONL store remains the source of truth even when external sync fails.

## API

- `GET /integrations/memory-gateway`: provider status and governance summary.
- `GET /memory`: list recent records.
- `GET /memory/search?query=...`: search approved local memory and include optional external provider matches.
- `POST /memory`: create an operator-approved memory record.

## MemOS Provider

MemOS can be enabled with `MEMOS_ENABLED=true`, `MEMOS_HOST`, `MEMOS_USER_ID` and `MEMOS_MEM_CUBE_ID`.

- Write sync uses `POST /product/add`.
- External retrieval uses `POST /product/search`.
- `MEMOS_REQUIRED=false` keeps agent delivery resilient when MemOS is offline.
- `MEMOS_REQUIRED=true` should be reserved for controlled environments where the MemOS server is actively monitored.

## Production Direction

The local JSONL provider is the safe baseline. MemOS is now available as a retrieval backend while preserving this policy layer as the source of truth for secret screening and approval.
