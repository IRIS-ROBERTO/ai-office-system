"""
Supabase — Persistência durável do sistema.

Divisão de responsabilidades:
  Redis Streams : eventos em tempo real (alta frequência, ephemeral)
  Supabase      : histórico consultável, estado durável, analytics

O cliente é um singleton thread-safe inicializado uma única vez na
primeira chamada a `get_supabase_client()` e reutilizado em todo o
processo.  Usa a service_role key para que o backend tenha acesso
irrestrito às tabelas (RLS é aplicado somente ao anon key do frontend).
"""

import asyncio
import logging
from typing import Optional

from supabase import create_client, Client

from backend.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_client: Optional[Client] = None
_lock: asyncio.Lock = asyncio.Lock()


async def get_supabase_client() -> Client:
    """
    Retorna o cliente Supabase singleton.

    Thread-safe: usa asyncio.Lock para garantir que apenas uma coroutine
    inicializa o cliente mesmo sob concorrência.

    Raises:
        ValueError : Se SUPABASE_URL ou SUPABASE_SERVICE_KEY estiverem vazios.
        Exception  : Propaga qualquer erro de conexão do supabase-py.
    """
    global _client

    if _client is not None:
        return _client

    async with _lock:
        # Double-checked locking — outra coroutine pode ter inicializado
        # enquanto esperávamos o lock.
        if _client is not None:
            return _client

        url = settings.SUPABASE_URL
        key = settings.SUPABASE_SERVICE_KEY

        if not url or not key:
            raise ValueError(
                "SUPABASE_URL e SUPABASE_SERVICE_KEY são obrigatórios. "
                "Defina-os no arquivo .env ou como variáveis de ambiente."
            )

        logger.info("Inicializando cliente Supabase em %s", url)
        _client = create_client(url, key)
        logger.info("Cliente Supabase inicializado com sucesso.")

    return _client


def reset_client() -> None:
    """
    Reseta o singleton (útil em testes ou ao trocar credenciais em runtime).
    """
    global _client
    _client = None
    logger.debug("Cliente Supabase resetado.")
