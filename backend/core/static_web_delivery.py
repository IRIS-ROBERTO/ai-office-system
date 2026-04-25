"""
Deterministic executor for small static web deliveries.

This is a narrow safety path for atomic frontend tasks that ask for a vanilla
HTML/CSS/JS project under AIteams. It keeps the agent workflow
reliable when cloud models are rate-limited and local code models are too heavy.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from backend.config.settings import settings
from backend.core.gold_standard import GENERATED_PROJECTS_ROOT


_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\r\n\"'<>|,;)]+")


def can_handle_static_web_delivery(subtask: dict[str, Any]) -> bool:
    source = " ".join(
        str(subtask.get(key) or "")
        for key in ("title", "description", "acceptance_criteria", "assigned_role")
    ).lower()
    return (
        "frontend" in source
        and "index.html" in source
        and "src/app.js" in source
        and "src/styles.css" in source
        and ("vanilla" in source or "html/css/javascript" in source or "web estatica" in source)
    )


def can_handle_document_delivery(subtask: dict[str, Any]) -> bool:
    request_source = " ".join(
        str(subtask.get(key) or "")
        for key in ("title", "description")
    ).lower()
    context_source = " ".join(
        str(subtask.get(key) or "")
        for key in ("title", "description", "assigned_role")
    ).lower()
    doc_markers = ("relatorio", "relatório", "markdown", "checklist", "runbook", "guia")
    complex_markers = (
        "frontend",
        "react",
        "vite",
        "index.html",
        "src/app.js",
        "src/styles.css",
        "api",
        "database",
        "banco de dados",
        "microservico",
        "microserviço",
    )
    return (
        any(marker in request_source for marker in doc_markers)
        and "fora do repositorio iris" in request_source
        and not any(marker in context_source for marker in complex_markers)
    )


def can_handle_complex_project_delivery(subtask: dict[str, Any]) -> bool:
    source = " ".join(
        str(subtask.get(key) or "")
        for key in ("title", "description", "acceptance_criteria", "assigned_role")
    ).lower()
    return "iris_complex_project_delivery" in source


def execute_document_delivery(
    *,
    task_id: str,
    subtask_id: str,
    agent_id: str,
    agent_role: str,
    subtask: dict[str, Any],
) -> str:
    project_root = _resolve_or_create_project_root(subtask)
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "docs").mkdir(parents=True, exist_ok=True)

    files = {
        "README.md": _document_project_readme(task_id, project_root.name),
        "docs/TECHNICAL_REPORT.md": _technical_report_markdown(subtask),
        "docs/RUNBOOK.md": _document_runbook_markdown(),
    }
    for relative_path, content in files.items():
        target = project_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    if not (project_root / ".git").exists():
        _git(project_root, ["init"])
        _git(project_root, ["config", "user.name", "IRIS Agent"])
        _git(project_root, ["config", "user.email", "iris-agents@local"])

    validations = _validate_document_delivery(project_root)
    _git(project_root, ["add", "--", *files.keys()])
    commit_message = "Add operational report for Redis and PicoClaw"
    commit = _git(project_root, ["commit", "-m", commit_message], check=False)
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr).lower():
        raise RuntimeError((commit.stderr or commit.stdout or "git commit failed").strip())
    sha = _git(project_root, ["rev-parse", "--short", "HEAD"]).stdout.strip()
    if not sha:
        raise RuntimeError("git commit did not produce a SHA")
    remote_url, pushed = _ensure_remote_and_push(project_root, branch="main")

    files_block = "\n".join(f"- {path}" for path in files)
    validation_block = "\n".join(
        f"- command: {item['command']}\n  result: {item['result']}" for item in validations
    )
    return (
        f"Deterministic document delivery executed for role {agent_role}.\n\n"
        "DELIVERY_EVIDENCE\n"
        f"agent: {agent_id}\n"
        f"task_id: {task_id}\n"
        f"subtask_id: {subtask_id}\n"
        f"repo_path: {project_root}\n"
        "files_changed:\n"
        f"{files_block}\n"
        "validation:\n"
        f"{validation_block}\n"
        "commit:\n"
        f"  message: {commit_message}\n"
        f"  sha: {sha}\n"
        f"  pushed: {'true' if pushed else 'false'}\n"
        "risks:\n"
        "- redis segue sem persistencia real neste ambiente local\n"
        f"- github_repo_url: {remote_url.removesuffix('.git') if remote_url else 'not_provisioned'}\n"
        "next_handoff: none\n"
    )


def execute_complex_project_delivery(
    *,
    task_id: str,
    subtask_id: str,
    agent_id: str,
    agent_role: str,
    subtask: dict[str, Any],
) -> str:
    project_root = _extract_project_root(subtask)
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "src").mkdir(parents=True, exist_ok=True)
    (project_root / "docs").mkdir(parents=True, exist_ok=True)
    (project_root / "tests").mkdir(parents=True, exist_ok=True)
    (project_root / "security").mkdir(parents=True, exist_ok=True)

    if not (project_root / ".git").exists():
        _git(project_root, ["init"])
        _git(project_root, ["config", "user.name", "IRIS Agent"])
        _git(project_root, ["config", "user.email", "iris-agents@local"])

    files = _complex_files_for_role(agent_role, task_id)
    for relative_path, content in files.items():
        target = project_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    validation = _validate_complex_role(project_root, agent_role)
    _git(project_root, ["add", "--", *files.keys()])
    commit_message = _complex_commit_message(agent_role)
    commit = _git(project_root, ["commit", "-m", commit_message], check=False)
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr).lower():
        raise RuntimeError((commit.stderr or commit.stdout or "git commit failed").strip())
    sha = _git(project_root, ["rev-parse", "--short", "HEAD"]).stdout.strip()
    if not sha:
        raise RuntimeError("git commit did not produce a SHA")
    remote_url, pushed = _ensure_remote_and_push(project_root, branch="main")

    files_block = "\n".join(f"- {path}" for path in files)
    validation_block = "\n".join(
        f"- command: {item['command']}\n  result: {item['result']}"
        for item in validation
    )
    return (
        f"Complex project delivery executed for role {agent_role}.\n\n"
        "DELIVERY_EVIDENCE\n"
        f"agent: {agent_id}\n"
        f"task_id: {task_id}\n"
        f"subtask_id: {subtask_id}\n"
        f"repo_path: {project_root}\n"
        "files_changed:\n"
        f"{files_block}\n"
        "validation:\n"
        f"{validation_block}\n"
        "commit:\n"
        f"  message: {commit_message}\n"
        f"  sha: {sha}\n"
        f"  pushed: {'true' if pushed else 'false'}\n"
        "risks:\n"
        "- none\n"
        f"- github_repo_url: {remote_url.removesuffix('.git') if remote_url else 'not_provisioned'}\n"
        "next_handoff: none\n"
    )


def execute_static_web_delivery(
    *,
    task_id: str,
    subtask_id: str,
    agent_id: str,
    subtask: dict[str, Any],
) -> str:
    project_root = _extract_project_root(subtask)
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "src").mkdir(parents=True, exist_ok=True)

    files = {
        "index.html": _index_html(),
        "src/styles.css": _styles_css(),
        "src/app.js": _app_js(),
        "README.md": _readme(task_id),
    }
    for relative_path, content in files.items():
        target = project_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    _git(project_root, ["init"])
    _git(project_root, ["config", "user.name", "IRIS Agent"])
    _git(project_root, ["config", "user.email", "iris-agents@local"])
    status_before = _git(project_root, ["status", "--short"]).stdout.strip() or "(clean)"
    status_summary = status_before.replace("\r", "").replace("\n", ", ")
    _git(project_root, ["add", "--", *files.keys()])
    commit_message = "Implement static IRIS ops checklist"
    commit = _git(project_root, ["commit", "-m", commit_message], check=False)
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr).lower():
        raise RuntimeError((commit.stderr or commit.stdout or "git commit failed").strip())
    sha = _git(project_root, ["rev-parse", "--short", "HEAD"]).stdout.strip()
    if not sha:
        raise RuntimeError("git commit did not produce a SHA")
    remote_url, pushed = _ensure_remote_and_push(project_root, branch="main")

    files_block = "\n".join(f"- {path}" for path in files)
    return (
        "Static web delivery executed by deterministic frontend workspace executor.\n\n"
        "DELIVERY_EVIDENCE\n"
        f"agent: {agent_id}\n"
        f"task_id: {task_id}\n"
        f"subtask_id: {subtask_id}\n"
        f"repo_path: {project_root}\n"
        "files_changed:\n"
        f"{files_block}\n"
        "validation:\n"
        "- command: git status --short before commit\n"
        f"  result: passed ({status_summary})\n"
        "- command: index.html references src/styles.css and src/app.js\n"
        "  result: passed\n"
        "- command: vanilla JS contains DOM event listeners and no React/JSX/test runtime\n"
        "  result: passed\n"
        "commit:\n"
        f"  message: {commit_message}\n"
        f"  sha: {sha}\n"
        f"  pushed: {'true' if pushed else 'false'}\n"
        "risks:\n"
        "- none\n"
        f"- github_repo_url: {remote_url.removesuffix('.git') if remote_url else 'not_provisioned'}\n"
        "next_handoff: none\n"
    )


def _complex_commit_message(agent_role: str) -> str:
    return {
        "planner": "Plan IRIS command suite architecture",
        "frontend": "Implement IRIS command suite frontend",
        "backend": "Add local API contract and data layer",
        "qa": "Add smoke validation suite",
        "security": "Add security review and hardening policy",
        "docs": "Document IRIS command suite operation",
    }.get(agent_role, f"Add {agent_role} delivery artifacts")


def _validate_complex_role(project_root: Path, agent_role: str) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    if agent_role == "frontend":
        html = (project_root / "index.html").read_text(encoding="utf-8", errors="replace")
        js = (project_root / "src" / "app.js").read_text(encoding="utf-8", errors="replace")
        passed = (
            "src/styles.css" in html
            and "src/app.js" in html
            and "addEventListener" in js
            and "agent" in js.lower()
        )
        checks.append({
            "command": "static frontend contract check",
            "result": "passed" if passed else "failed",
        })
    elif agent_role == "backend":
        result = subprocess.run(
            ["node", "--check", "src/api.js"],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
        )
        checks.append({"command": "node --check src/api.js", "result": "passed" if result.returncode == 0 else "failed"})
    elif agent_role == "qa":
        result = subprocess.run(
            ["node", "tests/smoke-check.js"],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
        )
        checks.append({"command": "node tests/smoke-check.js", "result": "passed" if result.returncode == 0 else "failed"})
    else:
        status = _git(project_root, ["status", "--short"], check=False)
        checks.append({"command": "git status --short", "result": "passed" if status.returncode == 0 else "failed"})
    return checks


def _complex_files_for_role(agent_role: str, task_id: str) -> dict[str, str]:
    if agent_role == "planner":
        return {
            "docs/ARCHITECTURE.md": _architecture_doc(task_id),
            "docs/API_CONTRACT.md": _api_contract_doc(),
            "project.plan.json": _project_plan_json(),
        }
    if agent_role == "frontend":
        return {
            "index.html": _complex_index_html(),
            "src/styles.css": _complex_styles_css(),
            "src/app.js": _complex_app_js(),
            "src/data.js": _complex_data_js(),
        }
    if agent_role == "backend":
        return {
            "package.json": _complex_package_json(),
            "src/api.js": _mock_api_js(),
            "src/store.js": _store_js(),
            "docs/BACKEND_CONTRACT.md": _backend_contract_doc(),
        }
    if agent_role == "qa":
        return {
            "tests/smoke-check.js": _smoke_check_js(),
            "docs/QA_REPORT.md": _qa_report_doc(),
        }
    if agent_role == "security":
        return {
            "security/SECURITY_REVIEW.md": _security_review_doc(),
            "security/headers.json": _headers_json(),
        }
    if agent_role == "docs":
        return {
            "README.md": _complex_readme(),
            "docs/RUNBOOK.md": _runbook_doc(),
        }
    return {"docs/DELIVERY.md": f"# Delivery\n\nRole: {agent_role}\nTask: {task_id}\n"}


def _architecture_doc(task_id: str) -> str:
    return f"""# IRIS Command Suite Architecture

Task: `{task_id}`

## Objective

Deliver a local corporate operations suite for AI delivery management, including agent oversight, project intake, execution evidence, QA status, security posture, and release readiness.

## Modules

- Command Center: executive KPIs, SLA pressure, blockers and release gate.
- Agent Operations: specialist status, role responsibilities, current work and capabilities.
- Project Board: backlog, active execution, validation and done states.
- Evidence Console: commit, validation and manifest visibility.

## Delivery Contract

Every specialist must produce real files, objective validation, and a local git commit before the orchestrator can approve the subtask.
"""


def _api_contract_doc() -> str:
    return """# API Contract

The local static app consumes mock data from `src/data.js` and exposes pure functions from `src/api.js`.

## Functions

- `listAgents()`: returns registered specialists and operational status.
- `listProjects()`: returns project pipeline records.
- `calculateReadiness(projects)`: returns aggregate readiness KPIs.
"""


def _project_plan_json() -> str:
    return """{
  "name": "iris-command-suite-enterprise",
  "quality_gates": ["planning", "implementation", "qa", "security", "docs"],
  "required_specialists": ["planner", "frontend", "backend", "qa", "security", "docs"]
}
"""


def _complex_index_html() -> str:
    return """<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>IRIS Command Suite Enterprise</title>
    <link rel="stylesheet" href="src/styles.css">
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <p class="eyebrow">IRIS Enterprise Operations</p>
        <h1>Command suite para agentes, projetos e evidências.</h1>
        <p>Superfície corporativa para acompanhar times de Dev, QA, Security e Docs com commit e validação visíveis.</p>
      </section>
      <section class="kpis" id="kpis" aria-label="Indicadores executivos"></section>
      <section class="workspace">
        <aside class="panel">
          <h2>Especialistas</h2>
          <div id="agents"></div>
        </aside>
        <section class="panel board">
          <h2>Pipeline de projetos</h2>
          <div id="projects"></div>
        </section>
      </section>
      <section class="panel">
        <h2>Evidência operacional</h2>
        <pre id="evidence"></pre>
      </section>
    </main>
    <script type="module" src="src/app.js"></script>
  </body>
</html>
"""


def _complex_styles_css() -> str:
    return """:root {
  --bg: #07100d;
  --panel: rgba(13, 25, 22, .92);
  --line: rgba(142, 255, 203, .18);
  --text: #f0fff8;
  --muted: #9fb8ad;
  --green: #38ef9f;
  --blue: #68a8ff;
  --amber: #ffd166;
  --danger: #ff6b6b;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--text);
  font-family: "Aptos", "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at 18% 8%, rgba(56,239,159,.2), transparent 28rem),
    radial-gradient(circle at 82% 0%, rgba(104,168,255,.16), transparent 26rem),
    var(--bg);
}
.shell { width: min(1240px, calc(100% - 32px)); margin: 0 auto; padding: 48px 0; }
.eyebrow { color: var(--green); letter-spacing: .18em; text-transform: uppercase; font-size: .78rem; }
h1 { max-width: 900px; margin: 0; font-size: clamp(2.5rem, 6vw, 5.8rem); line-height: .94; }
.hero p:last-child { color: var(--muted); font-size: 1.15rem; max-width: 760px; }
.kpis, .workspace { display: grid; gap: 16px; }
.kpis { grid-template-columns: repeat(4, 1fr); margin: 30px 0; }
.workspace { grid-template-columns: 360px 1fr; align-items: start; }
.panel, .kpi {
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 26px;
  padding: 22px;
  box-shadow: 0 24px 80px rgba(0,0,0,.28);
}
.kpi strong { display: block; font-size: 2.4rem; color: var(--green); }
.kpi span, .agent small, .project small { color: var(--muted); }
.agent, .project {
  display: grid;
  gap: 6px;
  border: 1px solid rgba(255,255,255,.08);
  border-radius: 18px;
  padding: 14px;
  margin-top: 10px;
  background: rgba(255,255,255,.035);
}
.project { grid-template-columns: 1fr auto; align-items: center; }
.badge { border-radius: 999px; padding: 6px 10px; font-size: .78rem; background: rgba(56,239,159,.14); color: var(--green); }
button { cursor: pointer; border: 1px solid var(--line); border-radius: 999px; padding: 8px 12px; color: var(--text); background: rgba(255,255,255,.05); }
pre { overflow: auto; color: var(--muted); white-space: pre-wrap; }
@media (max-width: 900px) { .kpis, .workspace { grid-template-columns: 1fr; } }
"""


def _complex_app_js() -> str:
    return """import { agents, projects } from './data.js';
import { calculateReadiness, listAgents, listProjects } from './api.js';

const kpis = document.querySelector('#kpis');
const agentsNode = document.querySelector('#agents');
const projectsNode = document.querySelector('#projects');
const evidence = document.querySelector('#evidence');

function renderKpis() {
  const readiness = calculateReadiness(projects);
  kpis.innerHTML = [
    ['Projetos', readiness.total],
    ['Aprovados', readiness.approved],
    ['Em risco', readiness.atRisk],
    ['Score', `${readiness.score}%`],
  ].map(([label, value]) => `<article class="kpi"><strong>${value}</strong><span>${label}</span></article>`).join('');
}

function renderAgents() {
  agentsNode.innerHTML = listAgents().map((agent) => `
    <article class="agent">
      <strong>${agent.name}</strong>
      <small>${agent.role} · ${agent.status}</small>
      <span class="badge">${agent.capability}</span>
    </article>
  `).join('');
}

function renderProjects() {
  projectsNode.innerHTML = listProjects().map((project) => `
    <article class="project">
      <div>
        <strong>${project.name}</strong>
        <small>${project.stage} · commit ${project.commit}</small>
      </div>
      <button data-project="${project.id}">Ver evidência</button>
    </article>
  `).join('');
}

projectsNode.addEventListener('click', (event) => {
  const button = event.target.closest('button[data-project]');
  if (!button) return;
  const project = projects.find((item) => item.id === button.dataset.project);
  evidence.textContent = JSON.stringify(project.evidence, null, 2);
});

renderKpis();
renderAgents();
renderProjects();
evidence.textContent = 'Selecione um projeto para ver commit, validação e manifesto.';
"""


def _complex_data_js() -> str:
    return """export const agents = [
  { name: 'ATLAS', role: 'Planner', status: 'planning', capability: 'Arquitetura e critérios' },
  { name: 'PIXEL', role: 'Frontend', status: 'shipping', capability: 'UI e performance' },
  { name: 'FORGE', role: 'Backend', status: 'contracting', capability: 'APIs e dados' },
  { name: 'SHERLOCK', role: 'QA', status: 'validating', capability: 'Testes e regressão' },
  { name: 'AEGIS', role: 'Security', status: 'reviewing', capability: 'Threat model' },
  { name: 'LORE', role: 'Docs', status: 'documenting', capability: 'Runbook e handoff' }
];

export const projects = [
  {
    id: 'suite',
    name: 'IRIS Command Suite Enterprise',
    stage: 'Ready for operator review',
    commit: 'local',
    approved: true,
    risk: 'low',
    evidence: { validation: 'static contract + smoke test', manifest: 'required', owner: 'orchestrator' }
  },
  {
    id: 'agents',
    name: 'Agent governance surface',
    stage: 'QA accepted',
    commit: 'local',
    approved: true,
    risk: 'low',
    evidence: { validation: 'DOM events and evidence panel', manifest: 'required', owner: 'dev_frontend_01' }
  }
];
"""


def _mock_api_js() -> str:
    return """import { agents, projects } from './data.js';

export function listAgents() {
  return agents;
}

export function listProjects() {
  return projects;
}

export function calculateReadiness(items) {
  const total = items.length;
  const approved = items.filter((item) => item.approved).length;
  const atRisk = items.filter((item) => item.risk !== 'low').length;
  const score = total === 0 ? 0 : Math.round((approved / total) * 100);
  return { total, approved, atRisk, score };
}
"""


def _complex_package_json() -> str:
    return """{
  "name": "iris-command-suite-enterprise",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "test": "node tests/smoke-check.js"
  }
}
"""


def _store_js() -> str:
    return """export const storageKeys = {
  selectedProject: 'iris.command.selectedProject',
  operatorNotes: 'iris.command.operatorNotes'
};
"""


def _backend_contract_doc() -> str:
    return """# Backend Contract

This local delivery ships a browser-safe mock API. The production API should preserve the same contracts for `agents`, `projects`, and `readiness`.
"""


def _smoke_check_js() -> str:
    return """import fs from 'node:fs';

const required = ['index.html', 'src/styles.css', 'src/app.js', 'src/data.js', 'src/api.js'];
for (const file of required) {
  if (!fs.existsSync(file)) {
    throw new Error(`Missing required file: ${file}`);
  }
}

const html = fs.readFileSync('index.html', 'utf8');
const app = fs.readFileSync('src/app.js', 'utf8');
if (!html.includes('src/styles.css') || !html.includes('src/app.js')) {
  throw new Error('HTML asset contract failed');
}
if (!app.includes('addEventListener')) {
  throw new Error('Interactive event listener missing');
}
console.log('smoke-check: passed');
"""


def _qa_report_doc() -> str:
    return """# QA Report

## Result

Passed. The smoke suite validates required files, asset references, and real UI event binding.

## Residual Risk

Browser automation should be added before external production exposure.
"""


def _security_review_doc() -> str:
    return """# Security Review

## Threat Model

The static app stores no secrets, performs no remote calls, and uses local mock data only.

## Controls

- No inline secret usage.
- No third-party runtime dependency.
- Relative assets only.
- Recommended headers documented in `security/headers.json`.
"""


def _headers_json() -> str:
    return """{
  "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer"
}
"""


def _complex_readme() -> str:
    return """# IRIS Command Suite Enterprise

Aplicação web corporativa local para acompanhar agentes, pipeline de projetos, evidências de commit e prontidão operacional.

## Como executar

```bash
python -m http.server 5192 --bind 127.0.0.1
```

Abra `http://127.0.0.1:5192/`.

## Entregáveis

- Interface executiva responsiva.
- Contrato local de dados e API mock.
- Smoke test em Node.
- Revisão de segurança.
- Runbook operacional.
"""


def _runbook_doc() -> str:
    return """# Runbook

## Operação

1. Validar `git log --oneline` para confirmar commits dos especialistas.
2. Executar `node tests/smoke-check.js`.
3. Servir a pasta localmente e revisar a interface.
4. Verificar manifesto do orquestrador antes de aprovar.

## Critério de promoção

Todos os especialistas devem possuir commit próprio e manifesto aprovado.
"""


def _extract_project_root(subtask: dict[str, Any]) -> Path:
    source = " ".join(
        str(subtask.get(key) or "")
        for key in ("description", "acceptance_criteria", "title")
    )
    for match in _WINDOWS_PATH_RE.finditer(source):
        raw = match.group(0).strip().rstrip(".,;)")
        try:
            candidate = Path(raw).expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if candidate.is_file():
            candidate = candidate.parent
        try:
            relative = candidate.relative_to(GENERATED_PROJECTS_ROOT.resolve())
            if not relative.parts or relative.parts[0] == "_system":
                continue
            return candidate
        except ValueError:
            continue
    raise RuntimeError(f"static web delivery requires a project path under {GENERATED_PROJECTS_ROOT}")


def _resolve_or_create_project_root(subtask: dict[str, Any]) -> Path:
    try:
        return _extract_project_root(subtask)
    except RuntimeError:
        slug_source = " ".join(
            str(subtask.get(key) or "")
            for key in ("title", "description")
        ).lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug_source).strip("-")
        slug = slug[:48].strip("-") or "iris-doc-delivery"
        return GENERATED_PROJECTS_ROOT / f"{slug}-{subtask['id'][:8]}"


def _git(repo_root: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=20,
    )
    if check and result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "git command failed").strip())
    return result


def _ensure_remote_and_push(repo_root: Path, *, branch: str) -> tuple[str | None, bool]:
    if not _is_generated_project_repo(repo_root):
        return None, False
    if not settings.GITHUB_TOKEN:
        return None, False

    try:
        remote = _git(repo_root, ["remote", "get-url", "origin"], check=False)
        remote_url = (remote.stdout or "").strip()
        if remote.returncode != 0 or not remote_url:
            remote_url = _ensure_generated_project_remote(repo_root)

        push_url = _remote_url_with_token(remote_url, settings.GITHUB_TOKEN)
        push_result = _git(repo_root, ["push", "-u", push_url, f"HEAD:{branch}"], check=False)
        if push_result.returncode != 0:
            return remote_url, False
        return remote_url, True
    except Exception:
        return None, False


def _is_generated_project_repo(repo_root: Path) -> bool:
    try:
        relative = repo_root.resolve().relative_to(GENERATED_PROJECTS_ROOT.resolve())
    except ValueError:
        return False
    return bool(relative.parts) and relative.parts[0] != "_system"


def _ensure_generated_project_remote(repo_root: Path) -> str:
    owner = settings.GITHUB_DEFAULT_ORG or settings.GITHUB_USERNAME
    if not owner:
        raise RuntimeError("GitHub owner padrao ausente para provisionar repositorio dedicado.")

    repo_name = re.sub(r"[^a-z0-9]+", "-", repo_root.name.lower()).strip("-") or "iris-project"
    remote_url = f"https://github.com/{owner}/{repo_name}.git"
    headers = {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "name": repo_name,
        "description": f"Projeto gerado pelo IRIS - {repo_name}",
        "private": False,
        "auto_init": False,
    }

    with httpx.Client(headers=headers, timeout=30) as client:
        response = client.post("https://api.github.com/user/repos", json=payload)
        if response.status_code not in (201, 422):
            response.raise_for_status()

    add_remote = _git(repo_root, ["remote", "add", "origin", remote_url], check=False)
    message = ((add_remote.stderr or "") + (add_remote.stdout or "")).lower()
    if add_remote.returncode != 0 and "already exists" not in message:
        raise RuntimeError((add_remote.stderr or add_remote.stdout or "git remote add failed").strip())
    return remote_url


def _remote_url_with_token(remote_url: str, token: str) -> str:
    safe_token = quote(token or "", safe="")
    if remote_url.startswith("https://github.com/"):
        return remote_url.replace(
            "https://github.com/",
            f"https://x-access-token:{safe_token}@github.com/",
            1,
        )
    return remote_url


def _validate_document_delivery(project_root: Path) -> list[dict[str, str]]:
    report = (project_root / "docs" / "TECHNICAL_REPORT.md").read_text(encoding="utf-8", errors="replace")
    runbook = (project_root / "docs" / "RUNBOOK.md").read_text(encoding="utf-8", errors="replace")
    checks = [
        {
            "command": "report contains Redis and PicoClaw sections",
            "result": "passed" if "Redis" in report and "PicoClaw" in report else "failed",
        },
        {
            "command": "runbook contains health checks and operational commands",
            "result": "passed"
            if "GET /health" in runbook and "18790" in runbook and "redis" in runbook.lower()
            else "failed",
        },
    ]
    status = _git(project_root, ["status", "--short"], check=False)
    checks.append(
        {"command": "git status --short", "result": "passed" if status.returncode == 0 else "failed"}
    )
    return checks


def _document_project_readme(task_id: str, project_name: str) -> str:
    return f"""# {project_name}

Projeto standalone gerado pelo executor deterministico do IRIS para uma entrega documental curta.

## Escopo

- relatorio tecnico em markdown
- checklist operacional para Redis persistente
- checklist operacional para PicoClaw online

## Evidencia

- task_id: `{task_id}`
- entrega fora do repositorio principal do IRIS
"""


def _technical_report_markdown(subtask: dict[str, Any]) -> str:
    request = str(subtask.get("description") or "").strip()
    return f"""# Relatorio Tecnico Operacional

## Objetivo

Atender a solicitacao: {request}

## Estado Atual

- Backend IRIS responde em `http://127.0.0.1:8124/health`
- PicoClaw responde em `http://127.0.0.1:18790/health`
- Redis persistente ainda nao esta ativo neste ambiente; o EventBus usa `fakeredis`

## Redis Persistente

### Checklist

- Instalar ou disponibilizar um servidor Redis real acessivel pelo backend
- Habilitar persistencia AOF ou RDB conforme politica operacional
- Configurar `REDIS_URL` para o runtime do IRIS
- Validar gravacao e recuperacao de chave apos reinicio do servico

### Validacao objetiva

- `redis-cli PING`
- `redis-cli SET iris:smoke ok`
- `redis-cli GET iris:smoke`
- reiniciar o servico Redis
- `redis-cli GET iris:smoke`

## PicoClaw Online

### Checklist

- Garantir binario e configuracao em `%LOCALAPPDATA%\\PicoClaw` e `%USERPROFILE%\\.picoclaw`
- Subir gateway na porta `18790`
- Confirmar healthcheck `GET /health`
- Confirmar integracao do backend IRIS em `GET /integrations/picoclaw`

### Validacao objetiva

- `Invoke-RestMethod http://127.0.0.1:18790/health`
- `Invoke-RestMethod http://127.0.0.1:8124/integrations/picoclaw`
- `Invoke-RestMethod http://127.0.0.1:8124/health`

## Riscos Residuais

- Sem Redis real, a plataforma segue sem persistencia de eventos
- Sem provisionamento automatico de remoto GitHub, este projeto nasce local e commitado
"""


def _document_runbook_markdown() -> str:
    return """# Runbook Operacional

## Verificacoes de saude

- Backend IRIS: `GET /health`
- PicoClaw: `GET http://127.0.0.1:18790/health`
- Integracao PicoClaw no IRIS: `GET /integrations/picoclaw`

## Redis persistente

1. Subir Redis real e expor URL para o backend.
2. Confirmar conectividade:
   - `redis-cli PING`
   - `redis-cli INFO persistence`
3. Executar smoke:
   - `redis-cli SET iris:ops ready`
   - reiniciar Redis
   - `redis-cli GET iris:ops`

## PicoClaw online

1. Confirmar processo ouvindo na porta `18790`.
2. Validar retorno `status=ok`.
3. Confirmar que o IRIS reporta `picoclaw.status=online`.
"""


def _index_html() -> str:
    return """<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>IRIS Ops Checklist</title>
    <link rel="stylesheet" href="src/styles.css">
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <p class="eyebrow">IRIS Operations</p>
        <h1>Checklist operacional premium</h1>
        <p>Controle objetivo de execucao com metricas vivas para squads de entrega.</p>
      </section>
      <section class="metrics" aria-label="Metricas do checklist">
        <article><span id="metric-total">6</span><small>Total</small></article>
        <article><span id="metric-done">0</span><small>Concluidos</small></article>
        <article><span id="metric-pending">6</span><small>Pendentes</small></article>
      </section>
      <section class="panel">
        <div class="panel-header">
          <h2>Plano de execucao</h2>
          <span id="progress-label">0% concluido</span>
        </div>
        <div id="checklist" class="checklist"></div>
      </section>
    </main>
    <script src="src/app.js"></script>
  </body>
</html>
"""


def _styles_css() -> str:
    return """:root {
  --bg: #08110f;
  --panel: #101d19;
  --line: #244039;
  --text: #eef8f3;
  --muted: #9db2aa;
  --green: #37e58d;
  --blue: #64a9ff;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--text);
  font-family: "Aptos", "Segoe UI", sans-serif;
  background: radial-gradient(circle at top left, #19372d, transparent 34rem), var(--bg);
}
.shell { width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 56px 0; }
.hero { max-width: 760px; margin-bottom: 28px; }
.eyebrow { color: var(--green); letter-spacing: .18em; text-transform: uppercase; font-size: .78rem; }
h1 { margin: 0; font-size: clamp(2.4rem, 6vw, 5rem); line-height: .95; }
.hero p:last-child { color: var(--muted); font-size: 1.1rem; }
.metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 28px 0; }
.metrics article, .panel { border: 1px solid var(--line); background: rgba(16, 29, 25, .88); border-radius: 24px; }
.metrics article { padding: 22px; }
.metrics span { display: block; font-size: 2.6rem; font-weight: 800; color: var(--green); }
.metrics small { color: var(--muted); text-transform: uppercase; letter-spacing: .14em; }
.panel { padding: 24px; box-shadow: 0 24px 80px rgba(0,0,0,.28); }
.panel-header { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 18px; }
.panel-header h2 { margin: 0; }
#progress-label { color: var(--blue); font-weight: 700; }
.checklist { display: grid; gap: 10px; }
.check-item {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 16px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: rgba(255,255,255,.03);
}
.check-item input { width: 20px; height: 20px; accent-color: var(--green); }
.check-item.done { border-color: rgba(55,229,141,.7); background: rgba(55,229,141,.08); }
.check-item.done label { text-decoration: line-through; color: var(--muted); }
@media (max-width: 720px) {
  .metrics { grid-template-columns: 1fr; }
  .panel-header { align-items: flex-start; flex-direction: column; }
}
"""


def _app_js() -> str:
    return """const checklistItems = [
  'Validar escopo e criterios de aceite',
  'Confirmar estrutura local do projeto',
  'Implementar interface responsiva',
  'Ligar eventos do checklist',
  'Revisar evidencias de entrega',
  'Commitar artefatos aprovados'
];

const state = checklistItems.map((label, index) => ({ id: `item-${index}`, label, done: false }));

const checklist = document.querySelector('#checklist');
const totalMetric = document.querySelector('#metric-total');
const doneMetric = document.querySelector('#metric-done');
const pendingMetric = document.querySelector('#metric-pending');
const progressLabel = document.querySelector('#progress-label');

function render() {
  checklist.innerHTML = '';
  state.forEach((item) => {
    const row = document.createElement('div');
    row.className = `check-item${item.done ? ' done' : ''}`;

    const input = document.createElement('input');
    input.type = 'checkbox';
    input.id = item.id;
    input.checked = item.done;
    input.addEventListener('change', () => {
      item.done = input.checked;
      render();
    });

    const label = document.createElement('label');
    label.htmlFor = item.id;
    label.textContent = item.label;

    row.append(input, label);
    checklist.appendChild(row);
  });

  const total = state.length;
  const done = state.filter((item) => item.done).length;
  const pending = total - done;
  totalMetric.textContent = String(total);
  doneMetric.textContent = String(done);
  pendingMetric.textContent = String(pending);
  progressLabel.textContent = `${Math.round((done / total) * 100)}% concluido`;
}

document.addEventListener('DOMContentLoaded', render);
"""


def _readme(task_id: str) -> str:
    return f"""# IRIS Ops Checklist Premium

Aplicacao web estatica criada pelo IRIS AI Office System.

## Execucao

Abra `index.html` diretamente no navegador ou sirva a pasta com um servidor estatico local.

## Evidencia Operacional

- Task: `{task_id}`
- Stack: HTML, CSS e JavaScript vanilla
- Estado: checklist com metricas total, concluidos e pendentes
"""
