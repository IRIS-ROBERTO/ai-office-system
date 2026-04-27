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
        ("agent_governance_policy", check_agent_governance_policy),
        ("delivery_supervisor_gate", check_delivery_supervisor_gate),
        ("capability_access_broker", check_capability_access_broker),
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


def check_agent_governance_policy() -> None:
    from backend.core.agent_governance import (
        build_governance_policy,
        can_transition,
        get_role_permissions,
        assert_valid_transition,
    )

    policy = build_governance_policy()
    states = set(policy["states"])
    required_states = {
        "intake",
        "triage",
        "planning",
        "review",
        "dispatch",
        "execution",
        "validation",
        "archive",
    }
    missing_states = sorted(required_states - states)
    if missing_states:
        raise AssertionError("missing governance states: " + ", ".join(missing_states))

    if not can_transition("intake", "triage"):
        raise AssertionError("valid intake -> triage transition was blocked")
    if not can_transition("validation", "archive"):
        raise AssertionError("valid validation -> archive transition was blocked")
    if can_transition("intake", "execution"):
        raise AssertionError("invalid intake -> execution transition was allowed")

    try:
        assert_valid_transition("planning", "archive")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid planning -> archive transition did not raise")

    orchestrator = set(get_role_permissions("orchestrator")["permissions"])
    for permission in ("triage", "plan", "review", "dispatch", "audit", "commit"):
        if permission not in orchestrator:
            raise AssertionError(f"orchestrator missing permission: {permission}")

    backend = get_role_permissions("backend")
    if "execute" not in backend["permissions"] or "commit" not in backend["permissions"]:
        raise AssertionError("backend role must execute and commit implementation work")
    if "create_dedicated_repo" not in get_role_permissions("backend")["denied"]:
        raise AssertionError("backend role must not create dedicated repos directly")

    product_factory = get_role_permissions("product_factory")
    if not product_factory["can_create_dedicated_repo"]:
        raise AssertionError("product_factory must own dedicated repo creation for new products")


def check_delivery_supervisor_gate() -> None:
    from backend.core.delivery_evidence import EvidenceValidationResult, DeliveryEvidence
    from backend.core.delivery_supervisor import (
        classify_delivery_type,
        classify_repo_strategy,
        evaluate_delivery_supervisor,
    )

    platform_subtask = {
        "id": "governance-platform",
        "title": "Melhoria da plataforma",
        "description": "Implementar controle interno no repositorio principal.",
        "acceptance_criteria": "Deve ser platform_improvement com commit no repo principal.",
        "assigned_role": "backend",
    }
    product_subtask = {
        **platform_subtask,
        "id": "new-product",
        "title": "Criar app novo",
        "description": "Criar aplicacao nova com repositorio dedicado.",
    }

    platform_evidence = DeliveryEvidence(
        task_id="task",
        subtask_id="governance-platform",
        repo_path=str(ROOT),
        files_changed=["backend/core/example.py"],
        validation=[{"command": "pytest", "result": "passed"}],
        commit_message="test",
        commit_sha="abcdef1",
    )
    platform_result = EvidenceValidationResult(True, "ok", platform_evidence)

    if classify_delivery_type(platform_subtask) != "platform_improvement":
        raise AssertionError("platform improvement was misclassified")
    if classify_delivery_type(product_subtask) != "new_product":
        raise AssertionError("new product was misclassified")
    if classify_delivery_type({"title": "Entrega operacional", "description": "Implementar artefato."}) != "unspecified":
        raise AssertionError("unmarked delivery should remain unspecified until repo strategy is known")
    if classify_repo_strategy(str(ROOT)) != "main_repository":
        raise AssertionError("main repo strategy was misclassified")

    approved = evaluate_delivery_supervisor(
        evidence_result=platform_result,
        subtask=platform_subtask,
        agent_role="backend",
    )
    if not approved.approved:
        raise AssertionError("valid platform delivery was blocked: " + "; ".join(approved.reasons))

    wrong_repo = evaluate_delivery_supervisor(
        evidence_result=platform_result,
        subtask=product_subtask,
        agent_role="backend",
    )
    if wrong_repo.approved:
        raise AssertionError("new product in main repo was incorrectly approved")

    failed_evidence = evaluate_delivery_supervisor(
        evidence_result=EvidenceValidationResult(False, "missing evidence", None),
        subtask=platform_subtask,
        agent_role="backend",
    )
    if failed_evidence.approved:
        raise AssertionError("delivery without approved evidence was incorrectly approved")


def check_capability_access_broker() -> None:
    from backend.core import capability_access

    original_store = capability_access._STORE_PATH
    original_authz = capability_access._AUTHZ_LOG_PATH
    test_store = ROOT / ".runtime" / "regression-capability-access" / "requests.json"
    test_authz = ROOT / ".runtime" / "regression-capability-access" / "authorizations.json"
    capability_access._STORE_PATH = test_store
    capability_access._AUTHZ_LOG_PATH = test_authz
    try:
        if test_store.exists():
            test_store.unlink()
        if test_authz.exists():
            test_authz.unlink()

        web_request = capability_access.create_capability_request(
            agent_id="qa_01",
            agent_role="qa",
            task_id="task-web",
            resource_type="web",
            resource="http://127.0.0.1:8124",
            access_level="read",
            reason="Testar endpoint local da entrega solicitada.",
            duration_minutes=30,
        )
        if web_request["status"] != "pending":
            raise AssertionError("new capability request must start pending")
        if web_request["requires_human_approval"]:
            raise AssertionError("local web read should not require human approval")

        approved = capability_access.approve_capability_request(
            web_request["request_id"],
            approved_by="regression",
        )
        if approved["status"] != "approved":
            raise AssertionError("capability request was not approved")

        profile = capability_access.get_agent_access_profile("qa_01", agent_role="qa")
        if not profile["can_use_web"]:
            raise AssertionError("approved web access did not update agent profile")

        allowed = capability_access.authorize_capability_use(
            agent_id="qa_01",
            task_id="task-web",
            resource_type="web",
            resource="http://127.0.0.1:8124/health",
            access_level="read",
            tool_name="browser-use",
        )
        if not allowed["allowed"]:
            raise AssertionError("approved grant did not authorize matching web use")

        denied_control = capability_access.authorize_capability_use(
            agent_id="qa_01",
            task_id="task-web",
            resource_type="web",
            resource="http://127.0.0.1:8124/health",
            access_level="control",
            tool_name="browser-use",
        )
        if denied_control["allowed"]:
            raise AssertionError("read web grant should not authorize control")

        authz_log = capability_access.list_capability_authorizations(agent_id="qa_01")
        if authz_log["total"] < 2:
            raise AssertionError("authorization attempts were not logged")

        screen_request = capability_access.create_capability_request(
            agent_id="qa_01",
            agent_role="qa",
            task_id="task-screen",
            resource_type="screen",
            resource="primary-display",
            access_level="control",
            reason="Validar fluxo visual que nao possui API alternativa.",
            duration_minutes=15,
        )
        if screen_request["risk"] != "critical" or not screen_request["requires_human_approval"]:
            raise AssertionError("screen control must be critical and human-approved")

        try:
            capability_access.create_capability_request(
                agent_id="qa_01",
                agent_role="qa",
                resource_type="directory",
                resource=str(ROOT),
                access_level="control",
                reason="Invalid directory control request.",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("directory control access should be rejected")
    finally:
        capability_access._STORE_PATH = original_store
        capability_access._AUTHZ_LOG_PATH = original_authz
        if test_store.exists():
            test_store.unlink()
        if test_authz.exists():
            test_authz.unlink()
        if test_store.parent.exists():
            shutil.rmtree(test_store.parent, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
