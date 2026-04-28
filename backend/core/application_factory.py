"""
Application Factory for SCOUT insights.

IRIS improvements stay in the platform repository. Standalone products are
generated in their own repository under AIteams and pushed to GitHub with
exclusive commit history from the first delivery.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from backend.config.settings import settings
from backend.core.gold_standard import GENERATED_PROJECTS_ROOT
from backend.core.research_store import classify_insight_delivery


_ROOT = Path(__file__).resolve().parents[2]
_APP_ROOT = _ROOT / "generated-applications"
_GITHUB_API = "https://api.github.com"
_FACTORY_RUNTIME_DIR = _ROOT / ".runtime" / "product-factory"
_FACTORY_REGISTRY = _FACTORY_RUNTIME_DIR / "registry.jsonl"
_REQUIRED_PRODUCT_ARTIFACTS = {
    "README.md",
    "ROADMAP.md",
    "LICENSE",
    "index.html",
    "src/app.js",
    "src/styles.css",
    "src/data.js",
    "docs/ARCHITECTURE.md",
    "docs/RUNBOOK.md",
    "docs/MARKET_BRIEF.md",
    "security/SECURITY_REVIEW.md",
    "tests/smoke-check.js",
}


def create_application_from_insight(insight: dict[str, Any]) -> dict[str, Any]:
    """Generate, validate and commit an application from an insight."""
    category_id = str(insight.get("category_id") or "insight")
    title = str(insight.get("title") or category_id)
    slug = _slugify(f"{category_id}-{title}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    delivery_mode = classify_insight_delivery(category_id)
    standalone = delivery_mode["repo_strategy"] == "dedicated_repository"
    app_dir = (
        GENERATED_PROJECTS_ROOT / f"{stamp}-{slug}"
        if standalone
        else _APP_ROOT / f"{stamp}-{slug}"
    )
    app_dir.mkdir(parents=True, exist_ok=False)
    repo_root = _prepare_repo_root(app_dir, standalone=standalone)

    files = _build_files(insight, app_dir.name)
    written: list[Path] = []
    for relative_path, content in files.items():
        target = app_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)

    validation = _run_validation(app_dir)
    commit_message = f"SCOUT: create {slug} application"
    remote_url, remote_error = _try_ensure_repo_remote(repo_root) if standalone else (None, "")
    commit_sha, pushed, push_error = _commit_paths(
        written,
        commit_message,
        repo_root=repo_root,
        push=standalone and bool(remote_url),
        branch="main",
        remote_url=remote_url,
    )
    provisioning_error = "; ".join(item for item in (remote_error, push_error) if item)

    provisioning_gate = _build_repo_provisioning_gate(
        repo_root=repo_root,
        remote_url=remote_url,
        branch="main",
        commit_sha=commit_sha,
        pushed=pushed,
        repo_strategy=delivery_mode["repo_strategy"],
        provisioning_error=provisioning_error,
    )

    product_value_gate = _build_product_value_gate(
        insight=insight,
        app_dir=app_dir,
        files_changed=[str(path.relative_to(repo_root)).replace("\\", "/") for path in written],
        validation=validation,
        provisioning_gate=provisioning_gate,
        repo_strategy=delivery_mode["repo_strategy"],
    )

    result = {
        "status": "created",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "category_id": category_id,
        "application_name": title,
        "application_slug": app_dir.name,
        "application_path": str(app_dir),
        "repo_relative_path": _repo_relative_path(app_dir, repo_root),
        "repo_path": str(repo_root),
        "repo_strategy": delivery_mode["repo_strategy"],
        "project_kind": delivery_mode["project_kind"],
        "files_changed": [str(path.relative_to(repo_root)).replace("\\", "/") for path in written],
        "validation": validation,
        "commit_message": commit_message,
        "commit_sha": commit_sha,
        "pushed_to_github": pushed,
        "github_repo_url": remote_url.removesuffix(".git") if remote_url else None,
        "provisioning_gate": provisioning_gate,
        "product_value_gate": product_value_gate,
        "provisioning_error": provisioning_error,
    }
    _append_factory_registry(result)
    return result


def update_product_factory_delivery_status(
    *,
    application_slug: str,
    pushed_to_github: bool,
    github_repo_url: str | None = None,
) -> dict[str, Any] | None:
    """Persist the final remote delivery evidence after the API push step."""
    if not application_slug:
        return None

    rows = _read_factory_registry()
    updated: dict[str, Any] | None = None
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        if row.get("application_slug") != application_slug:
            continue

        row["pushed_to_github"] = bool(pushed_to_github)
        if github_repo_url:
            row["github_repo_url"] = github_repo_url

        gate = dict(row.get("provisioning_gate") or {})
        checks = dict(gate.get("checks") or {})
        checks["remote_delivery_confirmed"] = bool(pushed_to_github)
        if github_repo_url:
            checks["github_repo_url_present"] = True
        gate["checks"] = checks
        gate["failed_checks"] = [name for name, ok in checks.items() if not ok]
        gate["approved"] = not gate["failed_checks"]
        row["provisioning_gate"] = gate

        value_gate = dict(row.get("product_value_gate") or {})
        value_checks = dict(value_gate.get("checks") or {})
        if value_checks:
            app_dir = Path(str(row.get("application_path") or ""))
            if app_dir.exists():
                value_checks["required_artifacts_present"] = all(
                    (app_dir / artifact).exists()
                    for artifact in _REQUIRED_PRODUCT_ARTIFACTS
                )
            value_checks["repository_ready"] = bool(gate["approved"])
            value_gate["checks"] = value_checks
            value_gate["failed_checks"] = [name for name, ok in value_checks.items() if not ok]
            score = _score_product_value_checks(value_checks)
            value_gate["score"] = score
            value_gate["approved"] = score >= int(value_gate.get("threshold") or 85) and not any(
                name in value_gate["failed_checks"]
                for name in ("validation_passed", "required_artifacts_present", "repository_ready")
            )
            row["product_value_gate"] = value_gate

        updated = row
        rows[index] = row
        break

    if updated is None:
        return None

    _write_factory_registry(rows)
    return updated


def _prepare_repo_root(app_dir: Path, *, standalone: bool) -> Path:
    if not standalone:
        return _ROOT

    init = subprocess.run(
        ["git", "init"],
        cwd=app_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=20,
    )
    if init.returncode != 0:
        raise RuntimeError((init.stdout + "\n" + init.stderr).strip() or "git init failed")
    subprocess.run(
        ["git", "symbolic-ref", "HEAD", "refs/heads/main"],
        cwd=app_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    return app_dir


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
        "ROADMAP.md": _roadmap(title),
        "LICENSE": _license_text(),
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


def _commit_paths(
    paths: list[Path],
    commit_message: str,
    *,
    repo_root: Path,
    push: bool,
    branch: str,
    remote_url: str | None,
) -> tuple[str, bool, str]:
    relative_paths = [str(path.relative_to(repo_root)).replace("\\", "/") for path in paths]
    subprocess.run(["git", "add", "--", *relative_paths], cwd=repo_root, check=True, timeout=20)
    result = subprocess.run(
        ["git", "commit", "-m", commit_message, "--only", "--", *relative_paths],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stdout + "\n" + result.stderr).strip() or "git commit failed")
    pushed = False
    push_error = ""
    if push and remote_url:
        push_url = _remote_url_with_token(remote_url, settings.GITHUB_TOKEN)
        push_result = subprocess.run(
            ["git", "push", "-u", push_url, f"HEAD:{branch}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=60,
        )
        if push_result.returncode != 0:
            push_error = (push_result.stdout + "\n" + push_result.stderr).strip() or "git push failed"
        else:
            pushed = True
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=10,
    ).stdout.strip()
    return sha, pushed, push_error


def _try_ensure_repo_remote(repo_root: Path) -> tuple[str | None, str]:
    try:
        return _ensure_repo_remote(repo_root), ""
    except Exception as exc:
        return None, _human_github_error(exc)


def _ensure_repo_remote(repo_root: Path) -> str:
    if not settings.GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN ausente para criar repositório dedicado no GitHub")

    owner = settings.GITHUB_DEFAULT_ORG or settings.GITHUB_USERNAME
    repo_name = _slugify(repo_root.name)
    remote_url = f"https://github.com/{owner}/{repo_name}.git"
    headers = {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "name": repo_name,
        "description": f"Standalone product generated by IRIS SCOUT - {repo_name}",
        "private": False,
        "auto_init": False,
    }
    with httpx.Client(headers=headers, timeout=30) as client:
        response = client.post(f"{_GITHUB_API}/user/repos", json=payload)
        if response.status_code not in (201, 422):
            response.raise_for_status()

    add_remote = subprocess.run(
        ["git", "remote", "add", "origin", remote_url],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    if add_remote.returncode != 0 and "already exists" not in ((add_remote.stderr or "") + (add_remote.stdout or "")).lower():
        raise RuntimeError((add_remote.stdout + "\n" + add_remote.stderr).strip() or "git remote add failed")
    return remote_url


def _remote_url_with_token(remote_url: str, token: str) -> str:
    safe_token = quote(token or "", safe="")
    if remote_url.startswith("https://github.com/"):
        return remote_url.replace("https://github.com/", f"https://x-access-token:{safe_token}@github.com/", 1)
    return remote_url


def _human_github_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        try:
            payload = exc.response.json()
            message = str(payload.get("message") or exc.response.text)
            documentation_url = str(payload.get("documentation_url") or "")
        except Exception:
            message = exc.response.text
            documentation_url = ""
        if status == 403:
            return (
                "GitHub recusou criar repositorio dedicado: 403 Forbidden. "
                "O token precisa de permissao para criar repositorios "
                "(classic: repo/public_repo; fine-grained: Administration write no owner). "
                f"Detalhe: {message}. {documentation_url}"
            ).strip()
        return f"GitHub recusou criar repositorio dedicado: HTTP {status}. {message}".strip()
    return f"Falha ao preparar repositorio remoto dedicado: {exc}"


def _repo_relative_path(app_dir: Path, repo_root: Path) -> str:
    if repo_root == _ROOT:
        return str(app_dir.relative_to(_ROOT)).replace("\\", "/")
    return "."


def list_product_factory_registry(*, limit: int = 50) -> dict[str, Any]:
    rows = _read_factory_registry()
    rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    limited = rows[: max(1, min(limit, 200))]
    return {"total": len(rows), "returned": len(limited), "items": limited}


def test_product_factory_implementation(category_id: str) -> dict[str, Any]:
    """Run the correct post-implementation test for an insight delivery."""
    row = _latest_registry_item(category_id)
    if row is None:
        raise FileNotFoundError(category_id)

    project_kind = str(row.get("project_kind") or "")
    repo_strategy = str(row.get("repo_strategy") or "")
    app_dir = Path(str(row.get("application_path") or ""))

    if project_kind == "standalone_product" or repo_strategy == "dedicated_repository":
        checks = _run_validation(app_dir)
        test_kind = "standalone_product_smoke"
    else:
        checks = _run_platform_validation()
        test_kind = "platform_release_gate"

    passed = bool(checks) and all(item.get("result") == "passed" for item in checks)
    result = {
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "test_kind": test_kind,
        "passed": passed,
        "validation": checks,
    }
    updated = update_product_factory_test_result(
        application_slug=str(row.get("application_slug") or ""),
        test_result=result,
    )
    return {
        "category_id": category_id,
        "application_slug": row.get("application_slug"),
        "project_kind": project_kind,
        "repo_strategy": repo_strategy,
        "test_result": result,
        "registry_item": updated,
    }


def update_product_factory_test_result(
    *,
    application_slug: str,
    test_result: dict[str, Any],
) -> dict[str, Any] | None:
    if not application_slug:
        return None

    rows = _read_factory_registry()
    updated: dict[str, Any] | None = None
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        if row.get("application_slug") != application_slug:
            continue
        row["last_test_result"] = test_result
        row["validation"] = test_result.get("validation") or row.get("validation")

        value_gate = dict(row.get("product_value_gate") or {})
        checks = dict(value_gate.get("checks") or {})
        if checks:
            checks["validation_passed"] = bool(test_result.get("passed"))
            value_gate["checks"] = checks
            value_gate["failed_checks"] = [name for name, ok in checks.items() if not ok]
            score = _score_product_value_checks(checks)
            value_gate["score"] = score
            value_gate["approved"] = score >= int(value_gate.get("threshold") or 85) and not any(
                name in value_gate["failed_checks"]
                for name in ("validation_passed", "required_artifacts_present", "repository_ready")
            )
            row["product_value_gate"] = value_gate

        rows[index] = row
        updated = row
        break

    if updated is None:
        return None
    _write_factory_registry(rows)
    return updated


def get_product_factory_metrics() -> dict[str, Any]:
    rows = _read_factory_registry()
    if not rows:
        return {
            "total_products": 0,
            "by_repo_strategy": {},
            "by_project_kind": {},
            "provisioning_gate_pass_rate": 0.0,
            "github_push_rate": 0.0,
            "value_gate_pass_rate": 0.0,
            "average_value_score": 0.0,
        }

    by_repo_strategy: dict[str, int] = {}
    by_project_kind: dict[str, int] = {}
    gate_passed = 0
    value_gate_passed = 0
    value_score_total = 0
    pushed = 0

    for row in rows:
        strategy = str(row.get("repo_strategy") or "unknown")
        kind = str(row.get("project_kind") or "unknown")
        by_repo_strategy[strategy] = by_repo_strategy.get(strategy, 0) + 1
        by_project_kind[kind] = by_project_kind.get(kind, 0) + 1
        gate = row.get("provisioning_gate") or {}
        if gate.get("approved"):
            gate_passed += 1
        value_gate = row.get("product_value_gate") or {}
        if value_gate.get("approved"):
            value_gate_passed += 1
        value_score_total += int(value_gate.get("score") or 0)
        if row.get("pushed_to_github"):
            pushed += 1

    total = len(rows)
    return {
        "total_products": total,
        "by_repo_strategy": by_repo_strategy,
        "by_project_kind": by_project_kind,
        "provisioning_gate_pass_rate": round(gate_passed / total * 100, 1),
        "github_push_rate": round(pushed / total * 100, 1),
        "value_gate_pass_rate": round(value_gate_passed / total * 100, 1),
        "average_value_score": round(value_score_total / total, 1),
    }


def _latest_registry_item(category_id: str) -> dict[str, Any] | None:
    rows = [
        row for row in _read_factory_registry()
        if str(row.get("category_id") or "") == category_id
    ]
    if not rows:
        return None
    rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return rows[0]


def _run_platform_validation() -> list[dict[str, str]]:
    commands = [
        [sys.executable, "-m", "compileall", "backend"],
        [sys.executable, "scripts/regression_delivery_checks.py"],
        [_npm_executable(), "--prefix", "frontend", "run", "build"],
    ]
    checks: list[dict[str, str]] = []
    for command in commands:
        result = subprocess.run(
            command,
            cwd=_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=180,
        )
        checks.append({
            "command": " ".join(command),
            "result": "passed" if result.returncode == 0 else "failed",
            "output": ((result.stdout or "") + "\n" + (result.stderr or "")).strip()[-1200:],
        })
    return checks


def _npm_executable() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _build_product_value_gate(
    *,
    insight: dict[str, Any],
    app_dir: Path,
    files_changed: list[str],
    validation: list[dict[str, str]],
    provisioning_gate: dict[str, Any],
    repo_strategy: str,
) -> dict[str, Any]:
    potential = insight.get("product_potential") or {}
    top_projects = insight.get("top_projects") or []
    summary = insight.get("summary") or {}
    changed = set(files_changed)
    checks = {
        "market_score_present": int(potential.get("score") or 0) >= 70,
        "market_pitch_present": bool(str(potential.get("pitch") or "").strip()),
        "top_projects_present": len(top_projects) >= 3,
        "implementation_summary_present": all(
            str(summary.get(key) or "").strip()
            for key in ("o_que_e", "para_que_serve", "onde_usariamos", "o_que_implementariamos")
        ),
        "required_artifacts_present": _all_required_artifacts_present(_REQUIRED_PRODUCT_ARTIFACTS, changed),
        "validation_passed": bool(validation) and all(item.get("result") == "passed" for item in validation),
        "security_review_present": (app_dir / "security" / "SECURITY_REVIEW.md").exists(),
        "runbook_present": (app_dir / "docs" / "RUNBOOK.md").exists(),
        "repository_ready": bool((provisioning_gate or {}).get("approved")),
        "dedicated_repo_for_standalone": repo_strategy != "dedicated_repository"
        or bool((provisioning_gate or {}).get("checks", {}).get("origin_configured")),
    }
    score = _score_product_value_checks(checks)
    failed = [name for name, ok in checks.items() if not ok]
    return {
        "approved": score >= 85 and not any(
            name in failed
            for name in ("validation_passed", "required_artifacts_present", "repository_ready")
        ),
        "score": score,
        "failed_checks": failed,
        "checks": checks,
        "threshold": 85,
    }


def _score_product_value_checks(checks: dict[str, bool]) -> int:
    weights = {
        "market_score_present": 15,
        "market_pitch_present": 10,
        "top_projects_present": 10,
        "implementation_summary_present": 10,
        "required_artifacts_present": 15,
        "validation_passed": 15,
        "security_review_present": 7,
        "runbook_present": 6,
        "repository_ready": 7,
        "dedicated_repo_for_standalone": 5,
    }
    return sum(weight for name, weight in weights.items() if checks.get(name))


def _all_required_artifacts_present(required_files: set[str], changed_files: set[str]) -> bool:
    normalized = {path.replace("\\", "/").lstrip("./") for path in changed_files}
    for required in required_files:
        if required in normalized:
            continue
        if not any(path.endswith(f"/{required}") for path in normalized):
            return False
    return True


def _build_repo_provisioning_gate(
    *,
    repo_root: Path,
    remote_url: str | None,
    branch: str,
    commit_sha: str,
    pushed: bool,
    repo_strategy: str,
    provisioning_error: str = "",
) -> dict[str, Any]:
    checks = {
        "git_repo_initialized": (repo_root / ".git").exists(),
        "origin_configured": True,
        "main_branch_ready": _git_stdout(repo_root, ["branch", "--show-current"]) == branch,
        "head_commit_present": _git_stdout(repo_root, ["rev-parse", "--short", "HEAD"]) == commit_sha,
        "push_confirmed": True,
        "github_repo_url_present": True,
        "remote_delivery_confirmed": True,
    }
    if repo_strategy == "dedicated_repository":
        checks["origin_configured"] = _git_ok(repo_root, ["remote", "get-url", "origin"])
        checks["push_confirmed"] = bool(pushed)
        checks["github_repo_url_present"] = bool(remote_url)
        checks["remote_delivery_confirmed"] = bool(pushed)
    failed = [name for name, ok in checks.items() if not ok]
    return {
        "approved": not failed,
        "failed_checks": failed,
        "checks": checks,
        "error": provisioning_error,
    }


def _append_factory_registry(payload: dict[str, Any]) -> None:
    _FACTORY_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with _FACTORY_REGISTRY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _write_factory_registry(rows: list[dict[str, Any]]) -> None:
    _FACTORY_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows)
    _FACTORY_REGISTRY.write_text(payload, encoding="utf-8")


def _read_factory_registry() -> list[dict[str, Any]]:
    if not _FACTORY_REGISTRY.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in _FACTORY_REGISTRY.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _git_ok(repo_root: Path, args: list[str]) -> bool:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    return result.returncode == 0


def _git_stdout(repo_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


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
cd {app_slug}
npm test
python -m http.server 5179
```

Open `http://127.0.0.1:5179/`.

## Delivery

- Source: SCOUT insight
- Validation: `node --check src/app.js` and `node tests/smoke-check.js`
- Commit policy: standalone products use their own repository; IRIS improvements stay in the platform repository
"""


def _roadmap(title: str) -> str:
    return f"""# {title} Roadmap

## V0.1

- Publish functional static MVP
- Validate smoke test and repository provisioning gate
- Confirm market thesis against first operator feedback

## V0.2

- Add real data source instead of embedded insight snapshot
- Add onboarding flow and operator configuration
- Add basic analytics and feedback capture

## V1

- Production backend and persistence
- Subscription or pricing surface
- CI pipeline and release automation
"""


def _license_text() -> str:
    return """MIT License

Copyright (c) 2026 IRIS

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
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
