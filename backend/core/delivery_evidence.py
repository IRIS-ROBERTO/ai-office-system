"""
Delivery evidence parsing and deterministic validation.

Agents must include a DELIVERY_EVIDENCE block in every versionable delivery.
This module turns that block into structured data that the orchestrator can
validate before asking an LLM-based quality gate for judgment.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from backend.core.gold_standard import GENERATED_PROJECTS_ROOT


_SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("supabase_secret", re.compile(r"\bsb_secret_[A-Za-z0-9_-]{12,}\b", re.IGNORECASE)),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE)),
)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALLOWED_REPO_ROOTS = (_REPO_ROOT, GENERATED_PROJECTS_ROOT)


@dataclass
class DeliveryEvidence:
    agent: str = ""
    task_id: str = ""
    subtask_id: str = ""
    files_changed: list[str] = field(default_factory=list)
    validation: list[dict[str, str]] = field(default_factory=list)
    commit_message: str = ""
    commit_sha: str = ""
    repo_path: str = ""
    pushed: bool | None = None
    risks: list[str] = field(default_factory=list)
    next_handoff: str = ""
    raw: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def has_commit(self) -> bool:
        return bool(self.commit_sha and self.commit_message)

    @property
    def has_validation(self) -> bool:
        return bool(self.validation)


@dataclass
class EvidenceValidationResult:
    approved: bool
    feedback: str
    evidence: DeliveryEvidence | None = None


def parse_delivery_evidence(output_text: str) -> DeliveryEvidence | None:
    if not output_text:
        return None

    raw_block = _extract_delivery_block(output_text)
    source = raw_block or output_text
    evidence = DeliveryEvidence(raw=source.strip())

    evidence.agent = _read_scalar(source, "agent")
    evidence.task_id = _read_scalar(source, "task_id")
    evidence.subtask_id = _read_scalar(source, "subtask_id")
    evidence.repo_path = _read_scalar(source, "repo_path")
    evidence.commit_message = _read_nested_or_scalar(source, "commit", "message")
    evidence.commit_sha = _read_nested_or_scalar(source, "commit", "sha")
    evidence.next_handoff = _read_scalar(source, "next_handoff")

    pushed_value = _read_nested_or_scalar(source, "commit", "pushed")
    if pushed_value:
        evidence.pushed = pushed_value.lower() in {"true", "yes", "sim", "1"}

    evidence.files_changed = _read_list(source, "files_changed")
    evidence.risks = _read_list(source, "risks")
    evidence.validation = _read_validation(source)

    # Fallback: parse the direct output of github_commit_tool if the agent pasted it.
    if not evidence.commit_sha:
        sha_match = re.search(r"SHA:\s*([0-9a-f]{7,40})", source, re.IGNORECASE)
        if sha_match:
            evidence.commit_sha = sha_match.group(1)
    if not evidence.files_changed:
        files_match = re.search(r"Arquivos:\s*(.+)", source, re.IGNORECASE)
        if files_match:
            evidence.files_changed = [
                item.strip() for item in files_match.group(1).split(",") if item.strip()
            ]
    if not evidence.commit_sha:
        sha_match = _SHA_RE.search(source)
        if sha_match and "commit" in source.lower():
            evidence.commit_sha = sha_match.group(0)

    if not raw_block and not evidence.commit_sha and not evidence.files_changed:
        return None
    return evidence


def validate_delivery_evidence(
    output_text: str,
    *,
    task_id: str,
    subtask_id: str,
    require_commit: bool = True,
) -> EvidenceValidationResult:
    evidence = parse_delivery_evidence(output_text)
    if evidence is None:
        return EvidenceValidationResult(
            approved=False,
            feedback=(
                "Ausente bloco DELIVERY_EVIDENCE. A entrega precisa listar arquivos "
                "alterados, validação executada e commit."
            ),
        )

    issues: list[str] = []
    if require_commit and not evidence.commit_sha:
        issues.append("commit.sha ausente")
    if require_commit and not evidence.commit_message:
        issues.append("commit.message ausente")

    repo_root, repo_feedback = _resolve_evidence_repo_root(evidence)
    if repo_feedback:
        issues.append(repo_feedback)

    commit_exists = bool(repo_root and evidence.commit_sha and _commit_exists(evidence.commit_sha, repo_root))
    if require_commit and evidence.commit_sha and not commit_exists:
        issues.append(f"commit.sha nao existe no repositorio: {evidence.commit_sha}")
    if not evidence.files_changed:
        issues.append("files_changed vazio")
    if not evidence.validation:
        issues.append("validation vazio")
    if evidence.validation and not _validation_passed(evidence.validation):
        issues.append("validation sem resultado passed")
    if require_commit and evidence.commit_sha and evidence.files_changed and commit_exists and repo_root:
        missing = _files_missing_from_commit(evidence.commit_sha, evidence.files_changed, repo_root)
        if missing:
            issues.append("files_changed ausentes do commit: " + ", ".join(missing))
        secret_hits = _secret_hits_in_commit(evidence.commit_sha, repo_root)
        if secret_hits:
            issues.append("possivel segredo no commit: " + ", ".join(secret_hits))

    if evidence.task_id and evidence.task_id != task_id:
        issues.append(f"task_id divergente: {evidence.task_id}")
    if evidence.subtask_id and evidence.subtask_id != subtask_id:
        issues.append(f"subtask_id divergente: {evidence.subtask_id}")

    if issues:
        return EvidenceValidationResult(
            approved=False,
            feedback="Evidência de entrega incompleta: " + "; ".join(issues),
            evidence=evidence,
        )

    return EvidenceValidationResult(
        approved=True,
        feedback="Evidência de entrega válida.",
        evidence=evidence,
    )


def _commit_exists(sha: str, repo_root: Path) -> bool:
    if not sha or not _SHA_RE.fullmatch(sha.strip()):
        return False

    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{sha.strip()}^{{commit}}"],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except Exception:
        return False

    return result.returncode == 0


def _files_missing_from_commit(sha: str, files_changed: list[str], repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "show", "--name-only", "--format=", sha.strip()],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=5,
    )
    if result.returncode != 0:
        return files_changed

    committed = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    expected = {_normalize_file_for_repo(item, repo_root) for item in files_changed if item.strip()}
    expected.discard("")
    return sorted(expected - committed)


def _secret_hits_in_commit(sha: str, repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "show", "--format=", "--unified=0", sha.strip()],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=5,
    )
    if result.returncode != 0:
        return ["secret_scan_unavailable"]

    added_lines = [
        line[1:]
        for line in result.stdout.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    hits: set[str] = set()
    for line in added_lines:
        for label, pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                hits.add(label)
    return sorted(hits)


def _resolve_evidence_repo_root(evidence: DeliveryEvidence) -> tuple[Path | None, str | None]:
    if evidence.repo_path:
        try:
            candidate = Path(evidence.repo_path).expanduser().resolve()
            if candidate.is_file():
                candidate = candidate.parent
            if not candidate.exists():
                return None, f"repo_path inexistente: {evidence.repo_path}"
            if not _is_allowed_repo_root(candidate):
                return None, f"repo_path fora das raizes autorizadas: {evidence.repo_path}"
            root = _git_root(candidate)
            if root and _is_allowed_repo_root(root):
                return root, None
            return None, f"repo_path nao e repositorio git: {evidence.repo_path}"
        except Exception as exc:
            return None, f"repo_path invalido: {exc}"

    inferred = _infer_repo_root_from_files(evidence.files_changed)
    if inferred:
        return inferred, None
    return _REPO_ROOT, None


def _infer_repo_root_from_files(files_changed: list[str]) -> Path | None:
    for file_path in files_changed:
        raw = file_path.strip()
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            continue
        try:
            resolved = candidate.resolve()
        except Exception:
            continue
        if not _is_allowed_repo_root(resolved):
            continue
        cwd = resolved.parent if resolved.suffix else resolved
        root = _git_root(cwd)
        if root and _is_allowed_repo_root(root):
            return root
    return None


def _git_root(path: Path) -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=5,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip()).resolve()


def _is_allowed_repo_root(path: Path) -> bool:
    for root in _ALLOWED_REPO_ROOTS:
        try:
            relative = path.relative_to(root)
            if root == GENERATED_PROJECTS_ROOT and (not relative.parts or relative.parts[0] == "_system"):
                return False
            return True
        except ValueError:
            continue
    return False


def _normalize_file_for_repo(file_path: str, repo_root: Path) -> str:
    raw = file_path.strip().replace("\\", "/")
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        try:
            return str(candidate.resolve().relative_to(repo_root)).replace("\\", "/")
        except ValueError:
            return raw
    return raw.lstrip("/")


def _validation_passed(validation: list[dict[str, str]]) -> bool:
    for item in validation:
        result = str(item.get("result", "")).strip().lower()
        if result in {"passed", "pass", "ok", "success", "sucesso"}:
            return True
    return False


def _extract_delivery_block(text: str) -> str | None:
    marker = "DELIVERY_EVIDENCE"
    idx = text.find(marker)
    if idx == -1:
        return None
    block = text[idx + len(marker):].strip()
    next_section = re.search(r"\n#{1,6}\s+", block)
    if next_section:
        block = block[: next_section.start()].strip()
    return block


def _read_scalar(text: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}\s*:\s*(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _read_nested_or_scalar(text: str, parent: str, child: str) -> str:
    nested = re.search(
        rf"^\s*{re.escape(parent)}\s*:\s*\n(?P<body>(?:\s{{2,}}.+\n?)+)",
        text,
        re.MULTILINE,
    )
    if nested:
        body = nested.group("body")
        value = _read_scalar(body, child)
        if value:
            return value
    return _read_scalar(text, f"{parent}.{child}") or _read_scalar(text, child)


def _read_list(text: str, key: str) -> list[str]:
    block = _read_indented_block(text, key)
    if not block:
        value = _read_scalar(text, key)
        return [value] if value and value.lower() not in {"none", "nenhum", "n/a"} else []

    items: list[str] = []
    for line in block.splitlines():
        cleaned = line.strip()
        if cleaned.startswith("-"):
            item = cleaned[1:].strip()
            if item and item.lower() not in {"none", "nenhum", "n/a"}:
                items.append(item)
    return items


def _read_validation(text: str) -> list[dict[str, str]]:
    block = _read_indented_block(text, "validation")
    if not block:
        return []

    results: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in block.splitlines():
        cleaned = line.strip()
        if cleaned.startswith("-"):
            if current:
                results.append(current)
            current = {}
            cleaned = cleaned[1:].strip()
            if ":" in cleaned:
                key, value = cleaned.split(":", 1)
                current[key.strip()] = value.strip()
        elif ":" in cleaned:
            key, value = cleaned.split(":", 1)
            current[key.strip()] = value.strip()
    if current:
        results.append(current)
    return results


def _read_indented_block(text: str, key: str) -> str:
    lines = text.splitlines()
    start_index: int | None = None
    for index, line in enumerate(lines):
        if re.match(rf"^\s*{re.escape(key)}\s*:\s*$", line):
            start_index = index + 1
            break

    if start_index is None:
        return ""

    block: list[str] = []
    for line in lines[start_index:]:
        stripped = line.strip()
        if not stripped:
            if block:
                block.append(line)
            continue
        is_nested = bool(line[:1].isspace() or stripped.startswith("-"))
        if block and not is_nested and re.match(r"^[A-Za-z_][A-Za-z0-9_.-]*\s*:", stripped):
            break
        if not block and not is_nested and re.match(r"^[A-Za-z_][A-Za-z0-9_.-]*\s*:", stripped):
            break
        block.append(line)

    return "\n".join(block)
