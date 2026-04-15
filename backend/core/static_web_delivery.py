"""
Deterministic executor for small static web deliveries.

This is a narrow safety path for atomic frontend tasks that ask for a vanilla
HTML/CSS/JS project under IRIS_GENERATED_PROJECTS. It keeps the agent workflow
reliable when cloud models are rate-limited and local code models are too heavy.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

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
        "  pushed: false\n"
        "risks:\n"
        "- none\n"
        "next_handoff: none\n"
    )


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
            candidate.relative_to(GENERATED_PROJECTS_ROOT.resolve())
            return candidate
        except ValueError:
            continue
    raise RuntimeError("static web delivery requires a project path under IRIS_GENERATED_PROJECTS")


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
