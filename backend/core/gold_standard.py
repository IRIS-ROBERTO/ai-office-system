"""
IRIS Gold Standard for autonomous agent delivery.

This text is injected into agent tasks so every delivery follows the same
operational contract before any commit is accepted.
"""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATED_PROJECTS_ROOT = Path.home() / "Desktop" / "SUCESSOS!!!!!!!!!!!!!!!!!!!!!!!!!!" / "AIteams"
GENERATED_PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)


def build_gold_standard_prompt(*, role: str, agent_id: str) -> str:
    return (
        "## IRIS GOLD STANDARD - NAO NEGOCIAVEL\n"
        f"Agente: {agent_id} / role: {role}\n"
        f"Repositorio local autorizado: {REPO_ROOT}\n\n"
        f"Raiz autorizada para projetos gerados: {GENERATED_PROJECTS_ROOT}\n"
        "Quando a tarefa pedir uma aplicacao/projeto novo, crie uma pasta propria dentro dessa raiz "
        "e mantenha todos os arquivos, testes e commits desse projeto ali. "
        "Nao use a pasta reservada `_system`.\n\n"
        "Padrao de engenharia PhD para qualquer entrega versionavel:\n"
        "- Formular uma hipotese de solucao antes de editar.\n"
        "- Preservar rastreabilidade: arquivo real, diff, validacao objetiva, commit e risco residual.\n"
        "- Rejeitar output bonito sem artefato verificavel.\n\n"
        "Fluxo obrigatorio para qualquer entrega versionavel:\n"
        "1. Entender o escopo e listar arquivos que precisam mudar.\n"
        "2. Usar a tool `workspace_file` para ler, alterar e inspecionar arquivos reais do workspace.\n"
        "   Ao editar, informe task_id, agent_id, agent_role e team para registrar evidencias no execution log.\n"
        "3. Usar `workspace_file` action=`diff` ou action=`status` para confirmar mudancas reais.\n"
        "4. Executar validacao objetiva antes do commit:\n"
        "   - Python/backend: `workspace_file` action=`validate_py_compile` com file_paths alterados.\n"
        "   - Frontend/TypeScript/CSS: `workspace_file` action=`npm_build`.\n"
        "   - Aplicacao web estatica HTML/CSS/JS: validar links do index.html, usar JS vanilla "
        "sem React/JSX/build, manter testes fora do runtime e confirmar `workspace_file` status/diff.\n"
        "     O index.html deve referenciar os caminhos reais, por exemplo `src/styles.css` e `src/app.js`.\n"
        "5. Usar `github_commit` em modo local com:\n"
        f"   - repo_path: `{REPO_ROOT}` para alteracoes no IRIS, ou a raiz git/worktree que contem o projeto gerado em `{GENERATED_PROJECTS_ROOT}`\n"
        "   - file_paths: lista exata dos arquivos alterados\n"
        "   - commit_message: mensagem curta e verificavel\n"
        "   - push: true SEMPRE — o sistema injeta o token automaticamente para push ao GitHub.\n"
        "   - init_repo_if_missing: true para projetos novos em GENERATED_PROJECTS_ROOT.\n"
        "6. Nunca inventar SHA, arquivo, teste ou push. Se a tool falhar, reportar falha.\n"
        "7. Nao commitar arquivos fora do escopo da subtarefa.\n\n"
        "Formato final obrigatorio:\n"
        "DELIVERY_EVIDENCE\n"
        f"agent: {agent_id}\n"
        "task_id: <task_id recebido>\n"
        "subtask_id: <subtask_id recebido>\n"
        f"repo_path: {REPO_ROOT} | raiz_git_do_projeto_em_{GENERATED_PROJECTS_ROOT}\n"
        "files_changed:\n"
        "- path/real/alterado\n"
        "validation:\n"
        "- command: comando_real_executado\n"
        "  result: passed|failed\n"
        "commit:\n"
        "  message: mensagem_real_do_commit\n"
        "  sha: sha_real_retornado_pela_tool_github_commit\n"
        "  pushed: true\n"
        "risks:\n"
        "- none | risco_real\n"
        "next_handoff: none | proximo_agente\n"
    )
