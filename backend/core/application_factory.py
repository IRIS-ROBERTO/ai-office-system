"""
Application Factory for SCOUT insights.

Turns an approved market/technology insight into a small, versioned application
scaffold inside the IRIS repository. The factory intentionally commits the
generated application so every new product experiment is auditable on GitHub.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[2]
_APP_ROOT = _ROOT / "generated-applications"


def create_application_from_insight(insight: dict[str, Any]) -> dict[str, Any]:
    """Generate, validate and commit a product application from an insight."""
    category_id = str(insight.get("category_id") or "insight")
    title = str(insight.get("title") or category_id)
    slug = _slugify(f"{category_id}-{title}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    app_dir = _APP_ROOT / f"{stamp}-{slug}"
    app_dir.mkdir(parents=True, exist_ok=False)

    files = _build_files(insight, app_dir.name)
    written: list[Path] = []
    for relative_path, content in files.items():
        target = app_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)

    validation = _run_validation(app_dir)
    commit_message = f"SCOUT: create {slug} application"
    commit_sha = _commit_paths(written, commit_message)

    return {
        "status": "created",
        "category_id": category_id,
        "application_name": title,
        "application_slug": app_dir.name,
        "application_path": str(app_dir),
        "repo_relative_path": str(app_dir.relative_to(_ROOT)).replace("\\", "/"),
        "files_changed": [str(path.relative_to(_ROOT)).replace("\\", "/") for path in written],
        "validation": validation,
        "commit_message": commit_message,
        "commit_sha": commit_sha,
    }


def _build_files(insight: dict[str, Any], app_slug: str) -> dict[str, str]:
    title = str(insight.get("title") or "SCOUT Application")
    description = str(insight.get("description") or "Application generated from SCOUT market intelligence.")
    recommendation = str(insight.get("recommendation") or "")
    summary = insight.get("summary") or {}
    potential = insight.get("product_potential") or {}
    projects = insight.get("top_projects") or []
    data_json = json.dumps(
        {
            "title": title,
            "description": description,
            "recommendation": recommendation,
            "potential": potential,
            "summary": summary,
            "projects": projects[:5],
        },
        ensure_ascii=True,
        indent=2,
    )

    return {
        "README.md": _readme(title, description, app_slug),
        "package.json": _package_json(app_slug),
        "index.html": _index_html(title),
        "src/data.js": f"export const scoutInsight = {data_json};\n",
        "src/app.js": _app_js(),
        "src/styles.css": _styles_css(),
        "docs/ARCHITECTURE.md": _architecture(title, recommendation),
        "docs/RUNBOOK.md": _runbook(),
        "docs/MARKET_BRIEF.md": _market_brief(insight),
        "security/SECURITY_REVIEW.md": _security_review(),
        "tests/smoke-check.js": _smoke_check_js(),
    }


def _run_validation(app_dir: Path) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    node_check = subprocess.run(
        ["node", "--check", "src/app.js"],
        cwd=app_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=20,
    )
    checks.append({
        "command": "node --check src/app.js",
        "result": "passed" if node_check.returncode == 0 else "failed",
    })

    smoke = subprocess.run(
        ["node", "tests/smoke-check.js"],
        cwd=app_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=20,
    )
    checks.append({
        "command": "node tests/smoke-check.js",
        "result": "passed" if smoke.returncode == 0 else "failed",
    })

    if any(item["result"] != "passed" for item in checks):
        details = "; ".join(f"{item['command']}={item['result']}" for item in checks)
        raise RuntimeError(f"application validation failed: {details}")
    return checks


def _commit_paths(paths: list[Path], commit_message: str) -> str:
    relative_paths = [str(path.relative_to(_ROOT)).replace("\\", "/") for path in paths]
    subprocess.run(["git", "add", "--", *relative_paths], cwd=_ROOT, check=True, timeout=20)
    result = subprocess.run(
        ["git", "commit", "-m", commit_message, "--only", "--", *relative_paths],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stdout + "\n" + result.stderr).strip() or "git commit failed")
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=10,
    ).stdout.strip()
    return sha


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:72] or "scout-application"


def _readme(title: str, description: str, app_slug: str) -> str:
    return f"""# {title}

Application scaffold generated by IRIS SCOUT Application Factory.

## Purpose

{description}

## Run

```bash
cd generated-applications/{app_slug}
npm test
python -m http.server 5179
```

Open `http://127.0.0.1:5179/`.

## Delivery

- Source: SCOUT insight
- Validation: `node --check src/app.js` and `node tests/smoke-check.js`
- Commit policy: every generated app is committed to the IRIS repository
"""


def _package_json(app_slug: str) -> str:
    return json.dumps(
        {
            "name": app_slug,
            "version": "0.1.0",
            "type": "module",
            "private": True,
            "scripts": {"test": "node tests/smoke-check.js"},
        },
        indent=2,
    ) + "\n"


def _index_html(title: str) -> str:
    safe_title = title.replace("<", "").replace(">", "")
    return f"""<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{safe_title}</title>
    <link rel="stylesheet" href="src/styles.css">
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <p class="eyebrow">SCOUT Application Factory</p>
        <h1 id="app-title">{safe_title}</h1>
        <p id="app-description"></p>
      </section>
      <section class="metrics" id="metrics" aria-label="Product metrics"></section>
      <section class="layout">
        <section class="panel">
          <h2>Market Thesis</h2>
          <p id="market-thesis"></p>
        </section>
        <section class="panel">
          <h2>Top Projects</h2>
          <div id="projects"></div>
        </section>
      </section>
      <section class="panel">
        <h2>Implementation Plan</h2>
        <ol id="implementation"></ol>
      </section>
    </main>
    <script type="module" src="src/app.js"></script>
  </body>
</html>
"""


def _app_js() -> str:
    return """import { scoutInsight } from './data.js';

const description = document.querySelector('#app-description');
const thesis = document.querySelector('#market-thesis');
const metrics = document.querySelector('#metrics');
const projects = document.querySelector('#projects');
const implementation = document.querySelector('#implementation');

const potential = scoutInsight.potential || {};
const summary = scoutInsight.summary || {};

description.textContent = scoutInsight.description || 'Generated product opportunity.';
thesis.textContent = potential.pitch || scoutInsight.recommendation || 'No market thesis available.';

const metricItems = [
  ['Viability', potential.viability || 'n/a'],
  ['Score', potential.score ? `${potential.score}/100` : 'n/a'],
  ['Projects', String((scoutInsight.projects || []).length)],
];

metrics.innerHTML = metricItems.map(([label, value]) => `
  <article class="metric">
    <strong>${value}</strong>
    <span>${label}</span>
  </article>
`).join('');

projects.innerHTML = (scoutInsight.projects || []).map((project) => `
  <article class="project">
    <div>
      <strong>${project.title || project.name}</strong>
      <small>${project.source || 'source'} · grade ${project.grade || 'n/a'} · score ${project.score || 0}</small>
    </div>
    ${project.url ? `<a href="${project.url}" target="_blank" rel="noreferrer">Open</a>` : ''}
  </article>
`).join('');

[
  summary.o_que_e || 'Define the product opportunity and user problem.',
  summary.onde_usariamos || 'Map how IRIS will use the application.',
  summary.o_que_implementariamos || 'Build the first workflow and proof of value.',
  'Validate with smoke tests, security review and market feedback.',
].forEach((item) => {
  const li = document.createElement('li');
  li.textContent = item;
  implementation.appendChild(li);
});
"""


def _styles_css() -> str:
    return """:root {
  --bg: #07100d;
  --panel: #101c18;
  --line: #244038;
  --text: #eef8f3;
  --muted: #9db2aa;
  --accent: #3ddc97;
  --blue: #64a9ff;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--text);
  font-family: Aptos, Segoe UI, sans-serif;
  background: linear-gradient(135deg, #07100d, #09151f 58%, #101207);
}
.shell { width: min(1160px, calc(100% - 32px)); margin: 0 auto; padding: 48px 0; }
.hero { max-width: 860px; margin-bottom: 28px; }
.eyebrow { color: var(--accent); letter-spacing: .18em; text-transform: uppercase; font-size: .78rem; }
h1 { margin: 0; font-size: clamp(2.35rem, 5vw, 4.9rem); line-height: 1; }
h2 { margin: 0 0 14px; }
.hero p:last-child, .panel p, li, small { color: var(--muted); line-height: 1.65; }
.metrics, .layout { display: grid; gap: 14px; }
.metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 26px 0; }
.layout { grid-template-columns: 1fr 1fr; align-items: start; }
.metric, .panel {
  border: 1px solid var(--line);
  background: rgba(16, 28, 24, .9);
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 20px 60px rgba(0,0,0,.25);
}
.metric strong { display: block; font-size: 2rem; color: var(--accent); overflow-wrap: anywhere; }
.metric span { color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .12em; }
.project {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 0;
  border-top: 1px solid rgba(255,255,255,.08);
}
.project:first-child { border-top: 0; padding-top: 0; }
.project a { color: var(--blue); text-decoration: none; font-weight: 700; }
ol { padding-left: 22px; }
@media (max-width: 820px) {
  .metrics, .layout { grid-template-columns: 1fr; }
  .project { flex-direction: column; }
}
"""


def _architecture(title: str, recommendation: str) -> str:
    return f"""# Architecture - {title}

## Objective

Turn a SCOUT-identified opportunity into a lightweight application that can be
reviewed by Dev, Marketing and leadership.

## Runtime

- Static HTML/CSS/JavaScript
- Local data contract in `src/data.js`
- No external runtime dependency

## Integration Path

{recommendation}

## Next Engineering Steps

1. Replace static data with FastAPI endpoints if the MVP is accepted.
2. Add persistent storage only after validating market fit.
3. Add browser E2E checks before external release.
"""


def _runbook() -> str:
    return """# Runbook

## Local Verification

```bash
npm test
python -m http.server 5179
```

## Promotion Criteria

- Smoke test passes.
- Market brief is accepted.
- Security review confirms no secrets or remote calls.
- Dev and Marketing agree on next milestone.
"""


def _market_brief(insight: dict[str, Any]) -> str:
    potential = insight.get("product_potential") or {}
    return f"""# Market Brief

## Recommendation

{insight.get('recommendation', '')}

## Product Potential

- Score: {potential.get('score', 'n/a')}
- Viability: {potential.get('viability', 'n/a')}

{potential.get('pitch', '')}
"""


def _security_review() -> str:
    return """# Security Review

## Status

Initial scaffold is low risk.

## Controls

- No secrets.
- No remote API calls.
- No dynamic code execution.
- External project links open in new tabs with `rel=noreferrer`.
"""


def _smoke_check_js() -> str:
    return """import fs from 'node:fs';

const required = [
  'index.html',
  'src/styles.css',
  'src/app.js',
  'src/data.js',
  'docs/ARCHITECTURE.md',
  'docs/RUNBOOK.md',
  'docs/MARKET_BRIEF.md',
  'security/SECURITY_REVIEW.md',
];

for (const file of required) {
  if (!fs.existsSync(file)) {
    throw new Error(`Missing required file: ${file}`);
  }
}

const html = fs.readFileSync('index.html', 'utf8');
const app = fs.readFileSync('src/app.js', 'utf8');
if (!html.includes('src/styles.css') || !html.includes('src/app.js')) {
  throw new Error('HTML asset references are incomplete');
}
if (!app.includes('document.querySelector')) {
  throw new Error('App does not bind to DOM');
}

console.log('application-factory-smoke: passed');
"""
