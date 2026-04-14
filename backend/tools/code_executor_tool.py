"""
IRIS AI Office System — CodeExecutorTool
Gives SHERLOCK (QA) and FORGE (Backend) the ability to actually RUN code.

Security model:
  - Runs in an isolated subprocess with a hard 60-second timeout.
  - stdout + stderr captured and returned as a single string.
  - Working directory is a controlled tmp folder.
  - No network access restriction (agents need pip install to set up deps).
  - Dangerous shell operators (rm -rf, sudo, etc.) are blocked at input level.

Usage: agent calls the tool with the code string and (optional) language.
       Returns: execution output or error message.
"""
import logging
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_BLOCKED_PATTERNS = [
    "rm -rf", "sudo ", "shutdown", "reboot", "mkfs",
    "dd if=", ":(){:|:&};:", "chmod 777", "curl | bash", "wget | sh",
]


class CodeExecutorInput(BaseModel):
    code: str = Field(description="Código Python a ser executado")
    language: str = Field(default="python", description="Linguagem: 'python' ou 'bash'")
    timeout_seconds: int = Field(default=60, description="Timeout máximo em segundos (1-120)")


class CodeExecutorTool(BaseTool):
    """
    Executa código Python ou Bash em subprocesso isolado com timeout.
    SHERLOCK usa para rodar suítes de teste; FORGE usa para validar scripts.
    """

    name: str = "code_executor"
    description: str = (
        "Executa código Python ou Bash e retorna stdout + stderr. "
        "Use para rodar testes pytest, scripts de validação e snippets de código. "
        "Timeout máximo: 60 segundos. Não use para operações destrutivas."
    )
    args_schema: Type[BaseModel] = CodeExecutorInput

    def _run(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int = 60,
    ) -> str:
        # Safety check
        for blocked in _BLOCKED_PATTERNS:
            if blocked.lower() in code.lower():
                return f"❌ BLOQUEADO: padrão perigoso detectado: '{blocked}'"

        timeout_seconds = max(1, min(timeout_seconds, 120))

        with tempfile.TemporaryDirectory(prefix="iris_exec_") as tmpdir:
            try:
                if language == "python":
                    return self._run_python(code, tmpdir, timeout_seconds)
                elif language == "bash":
                    return self._run_bash(code, tmpdir, timeout_seconds)
                else:
                    return f"❌ Linguagem não suportada: {language}. Use 'python' ou 'bash'."
            except Exception as exc:
                logger.error("[CodeExecutorTool] Erro inesperado: %s", exc)
                return f"❌ Erro interno no executor: {exc}"

    def _run_python(self, code: str, tmpdir: str, timeout: int) -> str:
        script_path = Path(tmpdir) / "script.py"
        script_path.write_text(textwrap.dedent(code), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tmpdir,
        )
        return self._format_result(result)

    def _run_bash(self, code: str, tmpdir: str, timeout: int) -> str:
        result = subprocess.run(
            code,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tmpdir,
        )
        return self._format_result(result)

    def _format_result(self, result: subprocess.CompletedProcess) -> str:
        parts = []
        if result.returncode == 0:
            parts.append(f"✅ Exit code: 0")
        else:
            parts.append(f"❌ Exit code: {result.returncode}")

        if result.stdout:
            parts.append(f"\n📤 STDOUT:\n{result.stdout[:4000]}")
        if result.stderr:
            parts.append(f"\n⚠️ STDERR:\n{result.stderr[:2000]}")
        if not result.stdout and not result.stderr:
            parts.append("\n(sem output)")

        return "\n".join(parts)


# Ready-to-inject instance
code_executor_tool = CodeExecutorTool()
