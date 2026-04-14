"""
IRIS AI Office System — SupabaseQueryTool
Gives PRISM (Analytics) and ORACLE (Research) read access to real data.

Operations supported:
  - select: query any table with optional filters and limit
  - count:  count rows matching a condition
  - rpc:    call a stored procedure (for complex analytics)

Write operations are intentionally excluded — agents should not mutate
production data without explicit human approval.
"""
import json
import logging
from typing import Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class SupabaseQueryInput(BaseModel):
    table: str = Field(description="Nome da tabela no Supabase (ex: 'tasks', 'agents')")
    operation: str = Field(
        default="select",
        description="Operação: 'select', 'count', ou 'rpc'",
    )
    columns: str = Field(default="*", description="Colunas a retornar (ex: 'id,status,team')")
    filters: Optional[dict] = Field(
        default=None,
        description="Filtros como dict (ex: {'status': 'completed', 'team': 'dev'})",
    )
    limit: int = Field(default=50, description="Máximo de linhas retornadas (1-500)")
    rpc_name: Optional[str] = Field(default=None, description="Nome do RPC (apenas op='rpc')")
    rpc_params: Optional[dict] = Field(default=None, description="Parâmetros do RPC")


class SupabaseQueryTool(BaseTool):
    """
    Executa consultas de leitura no Supabase para análise de dados reais.
    PRISM usa para analisar conversões; ORACLE usa para pesquisa de mercado interna.
    """

    name: str = "supabase_query"
    description: str = (
        "Consulta dados reais do Supabase. Use para análise de métricas, "
        "histórico de tarefas, performance de agentes e dados de negócio. "
        "Suporta SELECT com filtros, COUNT e chamadas RPC. "
        "Tabelas disponíveis: tasks, agents, improvement_proposals, critical_analyses."
    )
    args_schema: Type[BaseModel] = SupabaseQueryInput

    def _run(
        self,
        table: str,
        operation: str = "select",
        columns: str = "*",
        filters: Optional[dict] = None,
        limit: int = 50,
        rpc_name: Optional[str] = None,
        rpc_params: Optional[dict] = None,
    ) -> str:
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            return "⚠️ Supabase não configurado. Defina SUPABASE_URL e SUPABASE_ANON_KEY no .env"

        try:
            from supabase import create_client
            client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
            limit = max(1, min(limit, 500))

            if operation == "count":
                query = client.table(table).select(columns, count="exact")
                if filters:
                    for col, val in filters.items():
                        query = query.eq(col, val)
                response = query.execute()
                return f"📊 Count em '{table}': {response.count} registros"

            elif operation == "rpc" and rpc_name:
                response = client.rpc(rpc_name, rpc_params or {}).execute()
                data = response.data or []
                return f"✅ RPC '{rpc_name}' executado:\n{json.dumps(data[:20], ensure_ascii=False, indent=2)}"

            else:  # select
                query = client.table(table).select(columns).limit(limit)
                if filters:
                    for col, val in filters.items():
                        query = query.eq(col, val)
                response = query.execute()
                data = response.data or []
                return (
                    f"✅ {len(data)} registros de '{table}':\n"
                    + json.dumps(data, ensure_ascii=False, indent=2)
                )

        except Exception as exc:
            logger.error("[SupabaseQueryTool] Erro: %s", exc)
            return f"❌ Erro ao consultar Supabase: {exc}"


# Ready-to-inject instance
supabase_query_tool = SupabaseQueryTool()
