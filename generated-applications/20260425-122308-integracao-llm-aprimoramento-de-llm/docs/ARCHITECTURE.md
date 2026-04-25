# Architecture - Aprimoramento de LLM

## Objective

Turn a SCOUT-identified opportunity into a lightweight application that can be
reviewed by Dev, Marketing and leadership.

## Runtime

- Static HTML/CSS/JavaScript
- Local data contract in `src/data.js`
- No external runtime dependency

## Integration Path

Avaliar 'claude-mem' como LLM alternativo/complementar para os agentes IRIS — 64 modelos identificados.

## Next Engineering Steps

1. Replace static data with FastAPI endpoints if the MVP is accepted.
2. Add persistent storage only after validating market fit.
3. Add browser E2E checks before external release.
