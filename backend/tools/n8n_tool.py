"""
IRIS AI Office System — N8NWorkflowTool
Gives PULSE (Social Media) and NOVA (Content) the ability to
trigger real automation workflows via n8n.

Workflow types supported:
  - publish_social : post to LinkedIn, X, Instagram via n8n Social node
  - send_email     : send email campaigns via n8n Email node
  - create_doc     : create Google Doc / Notion page via n8n
  - webhook        : trigger any webhook-based n8n workflow by ID

Requirements:
  N8N_BASE_URL=http://localhost:5678  (or your n8n host)
  N8N_API_KEY=<your n8n API key>
"""
import json
import logging
from typing import Optional, Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class N8NWorkflowInput(BaseModel):
    workflow_type: str = Field(
        description=(
            "Tipo de workflow: 'publish_social', 'send_email', "
            "'create_doc', ou 'webhook'"
        )
    )
    payload: dict = Field(
        description=(
            "Dados para o workflow. "
            "publish_social: {'platform': 'linkedin', 'content': '...', 'hashtags': [...]}. "
            "send_email: {'to': '...', 'subject': '...', 'body': '...'}. "
            "create_doc: {'title': '...', 'content': '...', 'destination': 'notion|gdocs'}. "
            "webhook: {'workflow_id': '...', 'data': {...}}."
        )
    )
    dry_run: bool = Field(
        default=False,
        description="Se True, simula o envio sem executar de verdade (para testes)",
    )


class N8NWorkflowTool(BaseTool):
    """
    Dispara workflows n8n para publicar conteúdo, enviar emails e automatizar ações.
    PULSE usa para publicar posts nas redes sociais.
    NOVA usa para distribuir conteúdo via email e documentos.
    """

    name: str = "n8n_workflow"
    description: str = (
        "Dispara workflows de automação via n8n. "
        "Use para publicar posts nas redes sociais, enviar emails de campanha, "
        "criar documentos no Notion/Google Docs. "
        "Tipos: publish_social, send_email, create_doc, webhook."
    )
    args_schema: Type[BaseModel] = N8NWorkflowInput

    def _run(
        self,
        workflow_type: str,
        payload: dict,
        dry_run: bool = False,
    ) -> str:
        n8n_url = getattr(settings, "N8N_BASE_URL", "http://localhost:5678")
        n8n_key = getattr(settings, "N8N_API_KEY", "")

        if dry_run:
            return (
                f"🧪 DRY RUN — workflow '{workflow_type}' não executado.\n"
                f"Payload que seria enviado: {json.dumps(payload, ensure_ascii=False, indent=2)}"
            )

        if not n8n_key:
            return (
                "⚠️ N8N_API_KEY não configurada. "
                "Adicione N8N_API_KEY=<sua_chave> no .env para habilitar publicação."
            )

        # Map workflow_type to n8n webhook path
        _WEBHOOK_MAP = {
            "publish_social": "/webhook/iris-social-publish",
            "send_email":     "/webhook/iris-email-send",
            "create_doc":     "/webhook/iris-doc-create",
            "webhook":        f"/webhook/{payload.get('workflow_id', 'iris-generic')}",
        }

        path = _WEBHOOK_MAP.get(workflow_type, "/webhook/iris-generic")
        url = f"{n8n_url}{path}"

        try:
            headers = {"Content-Type": "application/json"}
            if n8n_key:
                headers["X-N8N-API-KEY"] = n8n_key

            resp = httpx.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()

            logger.info("[N8NWorkflowTool] Workflow '%s' disparado com sucesso.", workflow_type)
            return (
                f"✅ Workflow '{workflow_type}' executado com sucesso.\n"
                f"Status: {resp.status_code}\n"
                f"Response: {resp.text[:500]}"
            )
        except httpx.ConnectError:
            return (
                f"⚠️ n8n não acessível em {n8n_url}. "
                f"Verifique se o n8n está rodando e N8N_BASE_URL está correto."
            )
        except httpx.HTTPStatusError as exc:
            return f"❌ Erro HTTP {exc.response.status_code}: {exc.response.text[:300]}"
        except Exception as exc:
            logger.error("[N8NWorkflowTool] Erro: %s", exc)
            return f"❌ Erro ao disparar workflow: {exc}"


# Ready-to-inject instance
n8n_workflow_tool = N8NWorkflowTool()
