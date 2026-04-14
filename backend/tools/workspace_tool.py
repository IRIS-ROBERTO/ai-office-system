"""
Workspace tool for IRIS agents.

Gives agents controlled read/write/diff/validation access to the local repo.
It is intentionally narrow: paths must stay inside the repository and sensitive
or generated folders are blocked.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Literal, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from backend.core.execution_trace import append_execution_log
from backend.core.gold_standard import GENERATED_PROJECTS_ROOT


REPO_ROOT = Path(__file__).resolve().parents[2]
BLOCKED_PARTS = {
    ".git",
    ".runtime",
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
}
BLOCKED_FILES = {
    ".env",
    ".env.local",
}


class WorkspaceInput(BaseModel):
    action: Literal[
        "read",
        "write",
        "append",
        "replace",
        "mkdir",
        "git_init",
        "diff",
        "status",
        "validate_py_compile",
        "npm_build",
    ] = Field(description="Operacao segura no workspace")
    path: Optional[str] = Field(default=None, description="Arquivo/pasta relativo ao repo ou dentro de IRIS_GENERATED_PROJECTS")
    content: Optional[str] = Field(default=None, description="Conteudo usado em write/append")
    old_text: Optional[str] = Field(default=None, description="Texto exato a substituir na action replace")
    new_text: Optional[str] = Field(default=None, description="Novo texto usado na action replace")
    file_paths: list[str] = Field(default_factory=list, description="Arquivos relativos usados em status/diff/validate")
    project_path: Optional[str] = Field(default=None, description="Raiz do projeto para git_init/status/diff/npm_build")
    task_id: Optional[str] = Field(default=None, description="Task id para emitir eventos de artefato")
    agent_id: Optional[str] = Field(default=None, description="Agent id para emitir eventos de artefato")
    agent_role: Optional[str] = Field(default=None, description="Role do agente para emitir eventos de artefato")
    team: str = Field(default="dev", description="Time do agente: dev ou marketing")


class WorkspaceTool(BaseTool):
    name: str = "workspace_file"
    description: str = (
        "Le, altera, inspeciona diff/status e valida arquivos reais do repositorio local IRIS. "
        "Use antes de github_commit. Actions: read, write, append, replace, diff, status, "
        "validate_py_compile, npm_build."
    )
    args_schema: Type[BaseModel] = WorkspaceInput

    def _run(
        self,
        action: str,
        path: Optional[str] = None,
        content: Optional[str] = None,
        old_text: Optional[str] = None,
        new_text: Optional[str] = None,
        file_paths: Optional[list[str]] = None,
        project_path: Optional[str] = None,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        agent_role: Optional[str] = None,
        team: str = "dev",
    ) -> str:
        paths = file_paths or ([] if path is None else [path])

        try:
            if action == "status":
                root, normalized = self._root_and_normalized(paths, project_path)
                return self._git(root, ["status", "--short", "--"] + normalized)
            if action == "diff":
                root, normalized = self._root_and_normalized(paths, project_path)
                return self._git(root, ["diff", "--"] + normalized)
            if action == "git_init":
                target_root = self._resolve_project_root(project_path or path)
                target_root.mkdir(parents=True, exist_ok=True)
                init = self._run_process(["git", "init"], cwd=target_root)
                return self._format_process("git init", init)
            if action == "validate_py_compile":
                return self._validate_py_compile(paths)
            if action == "npm_build":
                return self._npm_build(project_path)

            if not path:
                return "ERROR: path e obrigatorio para esta action."

            target = self._resolve_safe_path(path)
            if action == "mkdir":
                target.mkdir(parents=True, exist_ok=True)
                return f"OK: pasta garantida: {target}"
            if action == "read":
                if not target.exists():
                    return f"ERROR: Arquivo nao existe: {path}"
                return target.read_text(encoding="utf-8", errors="replace")[:12000]

            self._ensure_writable(target)
            if action == "write":
                if content is None:
                    return "ERROR: content e obrigatorio para write."
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                result = self._result_with_status(f"OK: write aplicado em {path}", [path])
                self._emit_artifact_events(task_id, agent_id, agent_role, team, path, result)
                return result

            if action == "append":
                if content is None:
                    return "ERROR: content e obrigatorio para append."
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("a", encoding="utf-8") as handle:
                    handle.write(content)
                result = self._result_with_status(f"OK: append aplicado em {path}", [path])
                self._emit_artifact_events(task_id, agent_id, agent_role, team, path, result)
                return result

            if action == "replace":
                if old_text is None or new_text is None:
                    return "ERROR: old_text e new_text sao obrigatorios para replace."
                if not target.exists():
                    return f"ERROR: Arquivo nao existe: {path}"
                current = target.read_text(encoding="utf-8", errors="replace")
                if old_text not in current:
                    return "ERROR: old_text nao encontrado; leia o arquivo e tente um trecho exato."
                target.write_text(current.replace(old_text, new_text, 1), encoding="utf-8")
                result = self._result_with_status(f"OK: replace aplicado em {path}", [path])
                self._emit_artifact_events(task_id, agent_id, agent_role, team, path, result)
                return result

            return f"ERROR: action nao suportada: {action}"
        except Exception as exc:
            return f"ERROR: workspace_file falhou: {exc}"

    def _root_and_normalized(self, paths: list[str], project_path: Optional[str] = None) -> tuple[Path, list[str]]:
        root = self._resolve_project_root(project_path) if project_path else self._discover_git_root(paths)
        normalized: list[str] = []
        for item in paths:
            safe = self._resolve_safe_path(item)
            normalized.append(str(safe.relative_to(root)).replace("\\", "/"))
        return root, normalized

    def _normalize_many(self, paths: list[str], project_path: Optional[str] = None) -> list[str]:
        return self._root_and_normalized(paths, project_path)[1]

    def _resolve_safe_path(self, path: str) -> Path:
        normalized = path.replace("\\", "/").strip()
        candidate = Path(normalized).expanduser()
        target = candidate.resolve() if candidate.is_absolute() else (REPO_ROOT / normalized.lstrip("/")).resolve()

        if not self._is_allowed_root(target):
            generated_candidate = (GENERATED_PROJECTS_ROOT / normalized.lstrip("/")).resolve()
            if self._is_allowed_root(generated_candidate):
                target = generated_candidate
            else:
                raise RuntimeError(f"path fora das raizes autorizadas: {path}")

        rel_parts = set(target.parts)
        if rel_parts & BLOCKED_PARTS:
            raise RuntimeError(f"path bloqueado: {path}")
        if target.name in BLOCKED_FILES:
            raise RuntimeError(f"arquivo sensivel bloqueado: {path}")
        return target

    def _is_allowed_root(self, target: Path) -> bool:
        try:
            target.relative_to(REPO_ROOT)
            return True
        except ValueError:
            pass
        try:
            target.relative_to(GENERATED_PROJECTS_ROOT)
            return True
        except ValueError:
            return False

    def _resolve_project_root(self, project_path: Optional[str]) -> Path:
        if not project_path:
            return REPO_ROOT
        target = self._resolve_safe_path(project_path)
        return target if target.suffix == "" else target.parent

    def _discover_git_root(self, paths: list[str]) -> Path:
        if not paths:
            return REPO_ROOT
        first = self._resolve_safe_path(paths[0])
        cwd = first if first.is_dir() else first.parent
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd if cwd.exists() else REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            root = Path(result.stdout.strip()).resolve()
            if self._is_allowed_root(root):
                return root
        return REPO_ROOT if self._is_allowed_root(first) and first.is_relative_to(REPO_ROOT) else GENERATED_PROJECTS_ROOT

    def _ensure_writable(self, target: Path) -> None:
        suffix = target.suffix.lower()
        if suffix in {".exe", ".dll", ".bin", ".sqlite", ".db", ".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            raise RuntimeError(f"tipo de arquivo nao permitido para escrita: {target.name}")

    def _result_with_status(self, message: str, paths: list[str]) -> str:
        root, normalized = self._root_and_normalized(paths)
        status = self._git(root, ["status", "--short", "--"] + normalized)
        diff = self._git(root, ["diff", "--"] + normalized)
        return f"{message}\n\nSTATUS:\n{status}\n\nDIFF_PREVIEW:\n{diff[:6000]}"

    def _validate_py_compile(self, paths: list[str]) -> str:
        root, normalized = self._root_and_normalized(paths)
        py_files = [item for item in normalized if item.endswith(".py")]
        if not py_files:
            return "WARN: Nenhum arquivo .py informado para py_compile."
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", *py_files],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return self._format_process("py_compile", result)

    def _npm_build(self, project_path: Optional[str] = None) -> str:
        root = self._resolve_project_root(project_path) if project_path else REPO_ROOT / "frontend"
        install_summary = ""
        if (root / "package.json").exists() and not (root / "node_modules").exists():
            install = subprocess.run(
                ["npm", "install"],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=240,
            )
            install_summary = self._format_process("npm install", install)
            if install.returncode != 0:
                return install_summary

        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=180,
        )
        build_summary = self._format_process("npm run build", result)
        return "\n\n".join(part for part in [install_summary, build_summary] if part)

    def _git(self, cwd: Path, args: list[str]) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output = (result.stdout or result.stderr or "").strip()
        return output or "(sem alterações)"

    def _run_process(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def _format_process(self, label: str, result: subprocess.CompletedProcess[str]) -> str:
        status = "passed" if result.returncode == 0 else "failed"
        output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
        return f"{label}: {status}\nexit_code: {result.returncode}\n{output[:8000] if output else '(sem output)'}"

    def _emit_artifact_events(
        self,
        task_id: Optional[str],
        agent_id: Optional[str],
        agent_role: Optional[str],
        team: str,
        path: str,
        result_text: str,
    ) -> None:
        if not task_id or not agent_id:
            return

        diff_preview = result_text.split("DIFF_PREVIEW:", 1)[-1].strip()[:6000]
        append_execution_log(
            task_id,
            team,
            "code_artifact_updated",
            f"Agente alterou arquivo real: {path}",
            agent_id=agent_id,
            agent_role=agent_role,
            metadata={"file": path, "diff_preview": diff_preview},
        )


workspace_file_tool = WorkspaceTool()
