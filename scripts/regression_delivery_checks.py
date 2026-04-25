"""
Regression checks for deterministic delivery paths.

These checks protect the highest-value automation paths from falling back to
LLM-only behavior that can produce unverifiable evidence.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    failures: list[str] = []
    for name, check in [
        ("static_classifier", check_static_classifier),
        ("static_executor_evidence", check_static_executor_evidence),
    ]:
        try:
            check()
            print(f"[OK] {name}")
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"[FAIL] {name}: {exc}")

    if failures:
        print("\nRegression checks blocked:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


def _static_subtask() -> dict:
    return {
        "id": "regression-static-web",
        "title": "Implementar entrega principal com evidencias",
        "description": (
            "Teste funcional controlado: gerar uma pagina HTML estatica simples "
            "de status operacional com README e validacao smoke."
        ),
        "assigned_role": "frontend",
        "acceptance_criteria": (
            "Para entrega web estatica, index.html deve referenciar assets existentes, "
            "src/app.js deve ser JavaScript vanilla executavel direto no navegador, "
            "sem React/JSX sem build e sem codigo de teste misturado no runtime."
        ),
    }


def check_static_classifier() -> None:
    from backend.core.static_web_delivery import can_handle_static_web_delivery

    if not can_handle_static_web_delivery(_static_subtask()):
        raise AssertionError("simple static HTML task was not routed to deterministic executor")

    complex_subtask = {
        **_static_subtask(),
        "description": "Criar pagina HTML com backend FastAPI, database e autenticacao.",
    }
    if can_handle_static_web_delivery(complex_subtask):
        raise AssertionError("complex backend/database task was incorrectly routed as static HTML")


def check_static_executor_evidence() -> None:
    from backend.config.settings import settings
    from backend.core.delivery_evidence import validate_delivery_evidence
    from backend.core.gold_standard import GENERATED_PROJECTS_ROOT
    from backend.core.static_web_delivery import execute_static_web_delivery

    original_token = settings.GITHUB_TOKEN
    settings.GITHUB_TOKEN = ""
    output = ""
    project_root: Path | None = None
    try:
        task_id = "regression-static-task"
        subtask_id = "regression-static-web"
        output = execute_static_web_delivery(
            task_id=task_id,
            subtask_id=subtask_id,
            agent_id="dev_frontend_01",
            subtask=_static_subtask(),
        )
        result = validate_delivery_evidence(
            output,
            task_id=task_id,
            subtask_id=subtask_id,
            require_commit=True,
        )
        if not result.approved:
            raise AssertionError(result.feedback)
        if result.evidence is None:
            raise AssertionError("missing parsed evidence")

        project_root = Path(result.evidence.repo_path).resolve()
        project_root.relative_to(GENERATED_PROJECTS_ROOT.resolve())
        if project_root.name == "_system":
            raise AssertionError("static executor used reserved generated project folder")

        expected = ["index.html", "src/styles.css", "src/app.js", "README.md"]
        missing = [path for path in expected if not (project_root / path).exists()]
        if missing:
            raise AssertionError("missing generated files: " + ", ".join(missing))

        leaked = [path for path in ("README.md", "index.html") if (ROOT / path).exists()]
        if leaked:
            raise AssertionError("static executor leaked files into IRIS repo root: " + ", ".join(leaked))
    finally:
        settings.GITHUB_TOKEN = original_token
        if project_root and project_root.exists():
            shutil.rmtree(project_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
