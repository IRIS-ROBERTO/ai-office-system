"""
Deterministic delivery runner for IRIS agent subtasks.

This module does not replace CrewAI execution. It wraps the agent output with a
strict operational manifest so the orchestrator can distinguish:
- agent claimed success;
- platform verified evidence;
- delivery is actually ready for quality review.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.delivery_evidence import (
    EvidenceValidationResult,
    validate_delivery_evidence,
)
from backend.core.gold_standard import GENERATED_PROJECTS_ROOT


_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_ROOT = _ROOT / ".runtime" / "delivery-manifests"
_SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\r\n\"'<>|]+")


@dataclass
class DeliveryStage:
    name: str
    status: str
    message: str
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "passed"


@dataclass
class DeliveryManifest:
    task_id: str
    subtask_id: str
    agent_id: str
    agent_role: str
    team: str
    approved: bool
    feedback: str
    stages: list[DeliveryStage]
    evidence: dict[str, Any] | None
    output_preview: str
    created_at: str
    manifest_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stages"] = [asdict(stage) for stage in self.stages]
        return data


class DeliveryRunner:
    """Builds and persists deterministic delivery manifests for subtasks."""

    def evaluate_subtask_output(
        self,
        *,
        task_id: str,
        subtask: dict[str, Any],
        output_text: str,
        agent_id: str,
        agent_role: str,
        team: str,
        require_commit: bool = True,
    ) -> DeliveryManifest:
        subtask_id = str(subtask.get("id") or "")
        stages: list[DeliveryStage] = []

        stages.append(self._plan_lock_stage(subtask))
        stages.append(self._agent_output_stage(output_text))

        evidence_result = validate_delivery_evidence(
            output_text,
            task_id=task_id,
            subtask_id=subtask_id,
            require_commit=require_commit,
        )
        if not evidence_result.approved:
            repaired_output = self._repair_evidence_from_git(
                task_id=task_id,
                subtask_id=subtask_id,
                agent_id=agent_id,
                output_text=output_text,
                subtask=subtask,
            )
            if repaired_output:
                repaired_result = validate_delivery_evidence(
                    repaired_output,
                    task_id=task_id,
                    subtask_id=subtask_id,
                    require_commit=require_commit,
                )
                if repaired_result.approved:
                    output_text = repaired_output
                    evidence_result = repaired_result

        stages.extend(self._evidence_stages(evidence_result, require_commit=require_commit))
        functional_stage = self._functional_readiness_stage(evidence_result, subtask)
        if functional_stage:
            stages.append(functional_stage)

        required_failures = [
            stage for stage in stages if stage.required and not stage.passed
        ]
        approved = not required_failures
        feedback = (
            "Entrega deterministica aprovada para quality gate."
            if approved
            else "Entrega bloqueada: "
            + "; ".join(f"{stage.name}: {stage.message}" for stage in required_failures)
        )

        manifest = DeliveryManifest(
            task_id=task_id,
            subtask_id=subtask_id,
            agent_id=agent_id,
            agent_role=agent_role,
            team=team,
            approved=approved,
            feedback=feedback,
            stages=stages,
            evidence=evidence_result.evidence.to_dict() if evidence_result.evidence else None,
            output_preview=(output_text or "")[:1200],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        manifest.manifest_path = str(self._manifest_path(manifest.task_id, manifest.subtask_id))
        self._write_manifest(manifest)
        return manifest

    def _plan_lock_stage(self, subtask: dict[str, Any]) -> DeliveryStage:
        missing = [
            key
            for key in ("id", "title", "description", "acceptance_criteria", "assigned_role")
            if not str(subtask.get(key) or "").strip()
        ]
        if missing:
            return DeliveryStage(
                name="PLAN_LOCK",
                status="failed",
                message="Subtarefa sem campos obrigatorios: " + ", ".join(missing),
                metadata={"missing": missing},
            )
        return DeliveryStage(
            name="PLAN_LOCK",
            status="passed",
            message="Escopo, dono e criterio de aceite definidos.",
            metadata={
                "title": subtask.get("title"),
                "assigned_role": subtask.get("assigned_role"),
            },
        )

    def _agent_output_stage(self, output_text: str) -> DeliveryStage:
        output = (output_text or "").strip()
        if not output:
            return DeliveryStage(
                name="AGENT_OUTPUT",
                status="failed",
                message="Agente nao retornou output.",
            )
        lowered = output.lower()
        if lowered.startswith("erro:") or "subtarefa excedeu timeout" in lowered:
            return DeliveryStage(
                name="AGENT_OUTPUT",
                status="failed",
                message=output[:300],
                metadata={"output_length": len(output)},
            )
        return DeliveryStage(
            name="AGENT_OUTPUT",
            status="passed",
            message="Agente retornou output para avaliacao.",
            metadata={"output_length": len(output)},
        )

    def _evidence_stages(
        self,
        evidence_result: EvidenceValidationResult,
        *,
        require_commit: bool,
    ) -> list[DeliveryStage]:
        evidence = evidence_result.evidence
        if evidence is None:
            return [
                DeliveryStage(
                    name="EVIDENCE_PARSE",
                    status="failed",
                    message=evidence_result.feedback,
                ),
                DeliveryStage(
                    name="VALIDATION_VERIFY",
                    status="failed",
                    message="Nao ha validation no DELIVERY_EVIDENCE.",
                ),
                DeliveryStage(
                    name="COMMIT_VERIFY",
                    status="failed" if require_commit else "skipped",
                    message="Nao ha commit verificavel.",
                    required=require_commit,
                ),
            ]

        validation_status = "passed" if evidence.has_validation else "failed"
        commit_status = "passed" if evidence.has_commit else "failed"
        if evidence_result.approved:
            validation_message = "Validacao declarada e aceita pelo gate deterministico."
            commit_message = "Commit existe, contem arquivos declarados e esta dentro da raiz autorizada."
        else:
            validation_message = evidence_result.feedback
            commit_message = evidence_result.feedback

        return [
            DeliveryStage(
                name="EVIDENCE_PARSE",
                status="passed",
                message="DELIVERY_EVIDENCE parseado.",
                metadata={
                    "files_changed": evidence.files_changed,
                    "repo_path": evidence.repo_path,
                },
            ),
            DeliveryStage(
                name="VALIDATION_VERIFY",
                status=validation_status if evidence_result.approved else "failed",
                message=validation_message,
                metadata={"validation": evidence.validation},
            ),
            DeliveryStage(
                name="COMMIT_VERIFY",
                status=commit_status if evidence_result.approved else "failed",
                message=commit_message,
                required=require_commit,
                metadata={
                    "commit_sha": evidence.commit_sha,
                    "commit_message": evidence.commit_message,
                    "pushed": evidence.pushed,
                },
            ),
        ]

    def _functional_readiness_stage(
        self,
        evidence_result: EvidenceValidationResult,
        subtask: dict[str, Any],
    ) -> DeliveryStage | None:
        source = " ".join(
            str(subtask.get(key) or "")
            for key in ("title", "description", "acceptance_criteria")
        ).lower()
        web_markers = ("web", "frontend", "html", "css", "javascript", "interface", "responsiva")
        if not any(marker in source for marker in web_markers):
            return None

        evidence = evidence_result.evidence
        if evidence is None or not evidence_result.approved:
            return None

        try:
            repo_root = Path(evidence.repo_path).expanduser().resolve()
        except Exception as exc:
            return DeliveryStage(
                name="FUNCTIONAL_READINESS",
                status="failed",
                message=f"repo_path invalido para validacao funcional: {exc}",
            )

        index_path = repo_root / "index.html"
        if not index_path.exists():
            return DeliveryStage(
                name="FUNCTIONAL_READINESS",
                status="failed",
                message="Entrega web sem index.html na raiz do projeto.",
                metadata={"repo_path": str(repo_root)},
            )

        html = index_path.read_text(encoding="utf-8", errors="replace")
        referenced_assets = self._html_asset_refs(html)
        missing_assets: list[str] = []
        for asset in referenced_assets:
            target = (repo_root / asset).resolve()
            try:
                target.relative_to(repo_root)
            except ValueError:
                missing_assets.append(asset)
                continue
            if not target.exists():
                missing_assets.append(asset)

        issues: list[str] = []
        if missing_assets:
            issues.append("assets referenciados inexistentes: " + ", ".join(sorted(missing_assets)))

        js_files = [asset for asset in referenced_assets if asset.lower().endswith(".js")]
        if not js_files:
            js_files = [
                file_path
                for file_path in evidence.files_changed
                if file_path.lower().endswith(".js")
            ]

        js_checks = self._validate_static_js(repo_root, html, js_files)
        issues.extend(js_checks)

        if issues:
            return DeliveryStage(
                name="FUNCTIONAL_READINESS",
                status="failed",
                message="; ".join(issues),
                metadata={
                    "repo_path": str(repo_root),
                    "referenced_assets": referenced_assets,
                    "js_files": js_files,
                },
            )

        return DeliveryStage(
            name="FUNCTIONAL_READINESS",
            status="passed",
            message="Entrega web estatica possui assets referenciados e JS compativel com execucao direta.",
            metadata={
                "repo_path": str(repo_root),
                "referenced_assets": referenced_assets,
                "js_files": js_files,
            },
        )

    def _html_asset_refs(self, html: str) -> list[str]:
        refs: list[str] = []
        for match in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html, re.IGNORECASE):
            raw = match.group(1).strip()
            lowered = raw.lower()
            if not raw or lowered.startswith(("http://", "https://", "data:", "mailto:", "#")):
                continue
            refs.append(raw.lstrip("./").replace("\\", "/"))
        return refs

    def _validate_static_js(self, repo_root: Path, html: str, js_files: list[str]) -> list[str]:
        issues: list[str] = []
        html_lower = html.lower()
        for js_file in js_files:
            js_path = (repo_root / js_file).resolve()
            try:
                js_path.relative_to(repo_root)
            except ValueError:
                issues.append(f"javascript fora da raiz permitida: {js_file}")
                continue
            if not js_path.exists():
                continue
            js = js_path.read_text(encoding="utf-8", errors="replace")
            js_lower = js.lower()
            if any(marker in js for marker in ("test(", "expect(", "render(<")):
                issues.append(f"{js_file} contem codigo de teste misturado no runtime")
            if ("react." in js_lower or "usestate" in js_lower) and "react" not in html_lower:
                issues.append(f"{js_file} depende de React, mas index.html nao carrega React")
            if re.search(r"return\s*\(\s*<", js) and "babel" not in html_lower:
                issues.append(f"{js_file} contem JSX sem build ou Babel no index.html")
            if not any(marker in js_lower for marker in ("addeventlistener", "queryselector", "onclick", "onchange")):
                issues.append(f"{js_file} nao demonstra manipulacao DOM/eventos para interacao real")
        return issues

    def _repair_evidence_from_git(
        self,
        *,
        task_id: str,
        subtask_id: str,
        agent_id: str,
        output_text: str,
        subtask: dict[str, Any],
    ) -> str:
        sha_match = _SHA_RE.search(output_text or "")
        if not sha_match:
            return ""
        sha = sha_match.group(0)

        candidate_roots = self._candidate_repo_roots(subtask)
        for repo_root in candidate_roots:
            if not self._commit_exists(repo_root, sha):
                continue
            files = self._commit_files(repo_root, sha)
            if not files:
                continue
            commit_message = self._commit_message(repo_root, sha)
            status = self._git(repo_root, ["status", "--short"])
            validation_result = "passed" if status.returncode == 0 else "failed"
            files_block = "\n".join(f"- {item}" for item in files)
            return (
                f"{output_text.rstrip()}\n\n"
                "DELIVERY_EVIDENCE\n"
                f"agent: {agent_id}\n"
                f"task_id: {task_id}\n"
                f"subtask_id: {subtask_id}\n"
                f"repo_path: {repo_root}\n"
                "files_changed:\n"
                f"{files_block}\n"
                "validation:\n"
                "- command: git cat-file + git show + git status --short\n"
                f"  result: {validation_result}\n"
                "commit:\n"
                f"  message: {commit_message}\n"
                f"  sha: {sha}\n"
                "  pushed: false\n"
                "risks:\n"
                "- evidence_repaired_from_verified_git_commit\n"
                "next_handoff: none\n"
            )

        return ""

    def _candidate_repo_roots(self, subtask: dict[str, Any]) -> list[Path]:
        source = " ".join(
            str(subtask.get(key) or "")
            for key in ("description", "acceptance_criteria", "title")
        )
        roots: list[Path] = []
        for match in _WINDOWS_PATH_RE.finditer(source):
            raw = match.group(0).strip().rstrip(".,;)")
            try:
                candidate = Path(raw).expanduser().resolve()
            except Exception:
                continue
            if candidate.exists() and self._is_allowed_generated_repo(candidate):
                roots.append(candidate)

        if GENERATED_PROJECTS_ROOT.exists():
            for candidate in GENERATED_PROJECTS_ROOT.iterdir():
                if candidate.is_dir() and self._is_allowed_generated_repo(candidate):
                    roots.append(candidate.resolve())

        unique: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            key = str(root).lower()
            if key not in seen:
                seen.add(key)
                unique.append(root)
        return unique

    def _is_allowed_generated_repo(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(GENERATED_PROJECTS_ROOT.resolve())
            return True
        except ValueError:
            return False

    def _commit_exists(self, repo_root: Path, sha: str) -> bool:
        result = self._git(repo_root, ["cat-file", "-e", f"{sha}^{{commit}}"])
        return result.returncode == 0

    def _commit_files(self, repo_root: Path, sha: str) -> list[str]:
        result = self._git(repo_root, ["show", "--name-only", "--format=", sha])
        if result.returncode != 0:
            return []
        return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]

    def _commit_message(self, repo_root: Path, sha: str) -> str:
        result = self._git(repo_root, ["log", "-1", "--format=%s", sha])
        if result.returncode != 0:
            return "recovered commit"
        return result.stdout.strip() or "recovered commit"

    def _git(self, repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=10,
        )

    def _manifest_path(self, task_id: str, subtask_id: str) -> Path:
        return _MANIFEST_ROOT / task_id / f"{subtask_id}.json"

    def _write_manifest(self, manifest: DeliveryManifest) -> Path:
        target = self._manifest_path(manifest.task_id, manifest.subtask_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        return target


delivery_runner = DeliveryRunner()
