"""
IRIS Key Pool — Pool de chaves OpenRouter para o AI Office System.

Provisiona e gerencia chaves nomeadas IRIS1, IRIS2, IRIS3...
via OpenRouter management key. Estado persistido no Supabase.

Migration SQL necessária:
    CREATE TABLE IF NOT EXISTS iris_key_pool (
        key_name TEXT PRIMARY KEY,
        key_hash TEXT NOT NULL,
        key_value TEXT NOT NULL,
        status TEXT DEFAULT 'active'
            CHECK (status IN ('active', 'exhausted', 'disabled')),
        limit_usd FLOAT DEFAULT 1.0,
        usage_usd FLOAT DEFAULT 0.0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        last_used TIMESTAMPTZ,
        exhausted_at TIMESTAMPTZ
    );
"""

import httpx
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

MANAGEMENT_KEY: str = settings.OPENROUTER_MANAGEMENT_KEY
OPENROUTER_API: str = "https://openrouter.ai/api/v1"
IRIS_KEY_PREFIX: str = "IRIS"
INITIAL_POOL_SIZE: int = 5          # IRIS1..IRIS5
KEY_LIMIT_USD: float = 1.0          # $1 por chave
EXHAUSTION_THRESHOLD: float = 0.95  # rotaciona quando 95% usado


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class IRISKeyPool:
    """Pool de chaves OpenRouter IRIS com persistência no Supabase."""

    def __init__(self) -> None:
        self._keys: list[dict] = []          # cache em memória
        self._current_index: int = 0
        self._lock = asyncio.Lock()
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Inicialização
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Carrega chaves existentes do Supabase. Provisiona IRIS1..IRIS5 se vazio."""
        async with self._lock:
            if self._initialized:
                return

            rows = await self._supabase_load_all()

            if not rows:
                logger.info("Nenhuma chave encontrada no pool. Provisionando %d chaves iniciais.", INITIAL_POOL_SIZE)
                for i in range(1, INITIAL_POOL_SIZE + 1):
                    name = f"{IRIS_KEY_PREFIX}{i}"
                    try:
                        key_data = await self.provision_new_key(name)
                        self._keys.append(key_data)
                        logger.info("Chave %s provisionada com sucesso.", name)
                    except Exception as exc:
                        logger.error("Falha ao provisionar %s: %s", name, exc)
            else:
                self._keys = rows
                logger.info("%d chave(s) carregada(s) do Supabase.", len(self._keys))

            # Posiciona no primeiro índice ativo
            self._current_index = self._find_first_active_index()
            self._initialized = True

    # ------------------------------------------------------------------
    # Obter chave ativa
    # ------------------------------------------------------------------

    async def get_active_key(self) -> str:
        """
        Retorna a chave ativa com quota restante.
        Se exaurida, marca como exhausted e avança para a próxima.
        Persiste estado no Supabase.
        Levanta RuntimeError se todas as chaves estiverem exauridas.
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            attempts = 0
            total = len(self._keys)

            while attempts < total:
                if self._current_index >= total:
                    self._current_index = 0

                key_data = self._keys[self._current_index]

                if key_data["status"] != "active":
                    self._current_index += 1
                    attempts += 1
                    continue

                # Verifica quota real na API
                try:
                    status = await self.check_key_status(key_data["key_value"])
                except Exception as exc:
                    logger.warning("Não foi possível verificar status da chave %s: %s", key_data["key_name"], exc)
                    status = {
                        "limit": key_data.get("limit_usd", KEY_LIMIT_USD),
                        "usage": key_data.get("usage_usd", 0.0),
                        "remaining": key_data.get("limit_usd", KEY_LIMIT_USD) - key_data.get("usage_usd", 0.0),
                        "is_exhausted": False,
                    }

                usage_ratio = (status["usage"] / status["limit"]) if status["limit"] > 0 else 1.0

                if status["is_exhausted"] or usage_ratio >= EXHAUSTION_THRESHOLD:
                    logger.info(
                        "Chave %s exaurida (%.1f%% usado). Marcando e avançando.",
                        key_data["key_name"],
                        usage_ratio * 100,
                    )
                    await self._mark_exhausted(self._current_index, status)
                    self._current_index += 1
                    attempts += 1
                    continue

                # Chave válida — atualiza last_used
                now = datetime.now(timezone.utc).isoformat()
                self._keys[self._current_index]["last_used"] = now
                self._keys[self._current_index]["usage_usd"] = status["usage"]
                await self._supabase_update(
                    key_name=key_data["key_name"],
                    fields={"last_used": now, "usage_usd": status["usage"]},
                )
                return key_data["key_value"]

            raise RuntimeError(
                "Todas as chaves IRIS estão exauridas. "
                "Use Ollama local ou provisione novas chaves."
            )

    # ------------------------------------------------------------------
    # Rotação forçada
    # ------------------------------------------------------------------

    async def rotate_key(self) -> str:
        """
        Força rotação para a próxima chave disponível.
        Retorna a key_value da nova chave ativa ou
        levanta RuntimeError instruindo fallback para Ollama local.
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            self._current_index += 1
            if self._current_index >= len(self._keys):
                self._current_index = 0

            # Encontra próxima ativa a partir do índice atual
            next_index = self._find_first_active_index(start=self._current_index)

            if next_index == -1:
                logger.warning("Todas as chaves IRIS exauridas. Fallback para Ollama local recomendado.")
                raise RuntimeError(
                    "Pool IRIS totalmente exaurido. "
                    "Roteie para Ollama local via model_gate.py."
                )

            self._current_index = next_index
            key_data = self._keys[self._current_index]
            logger.info("Chave rotacionada para %s.", key_data["key_name"])
            return key_data["key_value"]

    # ------------------------------------------------------------------
    # Provisionamento
    # ------------------------------------------------------------------

    async def provision_new_key(self, name: str) -> dict:
        """
        Cria nova chave via management key na API OpenRouter.
        Salva em Supabase com status 'active'.
        Retorna o dicionário da chave criada.
        """
        if not MANAGEMENT_KEY:
            raise ValueError(
                "OPENROUTER_MANAGEMENT_KEY não configurada. "
                "Adicione ao .env antes de provisionar chaves."
            )

        label = name.lower()  # IRIS1 -> iris1
        payload = {
            "name": name,
            "label": label,
            "limit": KEY_LIMIT_USD,
        }
        headers = {
            "Authorization": f"Bearer {MANAGEMENT_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OPENROUTER_API}/keys",
                json=payload,
                headers=headers,
            )

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Falha ao provisionar chave {name}: "
                f"HTTP {response.status_code} — {response.text}"
            )

        data = response.json()
        # A API retorna {"key": "<valor>", ...} ou aninhado em "data"
        raw_key: str = data.get("key") or (data.get("data") or {}).get("key", "")
        if not raw_key:
            raise RuntimeError(f"Resposta inesperada da API ao criar {name}: {data}")

        key_hash = raw_key[-4:]
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "key_name": name,
            "key_hash": key_hash,
            "key_value": raw_key,
            "status": "active",
            "limit_usd": KEY_LIMIT_USD,
            "usage_usd": 0.0,
            "created_at": now,
            "last_used": None,
            "exhausted_at": None,
        }

        await self._supabase_upsert(record)
        return record

    # ------------------------------------------------------------------
    # Verificação de status
    # ------------------------------------------------------------------

    async def check_key_status(self, key: str) -> dict:
        """
        Verifica quota restante via GET https://openrouter.ai/api/v1/auth/key.
        Retorna: {limit, usage, remaining, is_exhausted}
        """
        headers = {
            "Authorization": f"Bearer {key}",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{OPENROUTER_API}/auth/key",
                headers=headers,
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"Falha ao verificar chave: HTTP {response.status_code} — {response.text}"
            )

        raw = response.json()
        # Normaliza resposta — pode vir em "data" ou diretamente
        info: dict = raw.get("data", raw)

        limit: float = float(info.get("limit") or KEY_LIMIT_USD)
        usage: float = float(info.get("usage") or 0.0)
        remaining: float = limit - usage
        is_exhausted: bool = remaining <= 0 or (usage / limit >= EXHAUSTION_THRESHOLD if limit > 0 else True)

        return {
            "limit": limit,
            "usage": usage,
            "remaining": remaining,
            "is_exhausted": is_exhausted,
        }

    # ------------------------------------------------------------------
    # Status do pool (para /health)
    # ------------------------------------------------------------------

    async def get_pool_status(self) -> dict:
        """
        Retorna status completo de todas as chaves para o /health endpoint.
        """
        if not self._initialized:
            await self.initialize()

        keys_status = []
        for k in self._keys:
            keys_status.append({
                "key_name": k["key_name"],
                "key_hash": k.get("key_hash", "????"),
                "status": k.get("status", "unknown"),
                "limit_usd": k.get("limit_usd", KEY_LIMIT_USD),
                "usage_usd": k.get("usage_usd", 0.0),
                "remaining_usd": round(
                    k.get("limit_usd", KEY_LIMIT_USD) - k.get("usage_usd", 0.0), 4
                ),
                "last_used": k.get("last_used"),
                "exhausted_at": k.get("exhausted_at"),
            })

        active_count = sum(1 for k in self._keys if k.get("status") == "active")
        exhausted_count = sum(1 for k in self._keys if k.get("status") == "exhausted")
        disabled_count = sum(1 for k in self._keys if k.get("status") == "disabled")

        current_key_name: Optional[str] = None
        if self._keys and 0 <= self._current_index < len(self._keys):
            current_key_name = self._keys[self._current_index].get("key_name")

        return {
            "pool_size": len(self._keys),
            "active": active_count,
            "exhausted": exhausted_count,
            "disabled": disabled_count,
            "current_key": current_key_name,
            "exhaustion_threshold": EXHAUSTION_THRESHOLD,
            "key_limit_usd": KEY_LIMIT_USD,
            "keys": keys_status,
        }

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _find_first_active_index(self, start: int = 0) -> int:
        """Retorna o índice da primeira chave ativa a partir de `start`. -1 se nenhuma."""
        total = len(self._keys)
        for offset in range(total):
            idx = (start + offset) % total
            if self._keys[idx].get("status") == "active":
                return idx
        return -1

    async def _mark_exhausted(self, index: int, status: dict) -> None:
        """Marca chave no índice como exhausted no cache e no Supabase."""
        now = datetime.now(timezone.utc).isoformat()
        self._keys[index]["status"] = "exhausted"
        self._keys[index]["usage_usd"] = status.get("usage", self._keys[index].get("usage_usd", 0.0))
        self._keys[index]["exhausted_at"] = now

        await self._supabase_update(
            key_name=self._keys[index]["key_name"],
            fields={
                "status": "exhausted",
                "usage_usd": self._keys[index]["usage_usd"],
                "exhausted_at": now,
            },
        )

    # ------------------------------------------------------------------
    # Camada Supabase
    # ------------------------------------------------------------------

    def _supabase_client(self):
        """Retorna cliente Supabase. Importação lazy para evitar ciclo."""
        try:
            from supabase import create_client
            return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        except Exception as exc:
            raise RuntimeError(f"Não foi possível conectar ao Supabase: {exc}") from exc

    async def _supabase_load_all(self) -> list[dict]:
        """Carrega todas as linhas da tabela iris_key_pool."""
        try:
            client = self._supabase_client()
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.table("iris_key_pool").select("*").execute(),
            )
            return response.data or []
        except Exception as exc:
            logger.error("Erro ao carregar iris_key_pool do Supabase: %s", exc)
            return []

    async def _supabase_upsert(self, record: dict) -> None:
        """Insere ou atualiza um registro na tabela iris_key_pool."""
        try:
            client = self._supabase_client()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: client.table("iris_key_pool").upsert(record).execute(),
            )
        except Exception as exc:
            logger.error("Erro ao fazer upsert em iris_key_pool: %s", exc)

    async def _supabase_update(self, key_name: str, fields: dict) -> None:
        """Atualiza campos específicos de uma chave pelo key_name."""
        try:
            client = self._supabase_client()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: (
                    client.table("iris_key_pool")
                    .update(fields)
                    .eq("key_name", key_name)
                    .execute()
                ),
            )
        except Exception as exc:
            logger.error("Erro ao atualizar chave %s no Supabase: %s", key_name, exc)


# ---------------------------------------------------------------------------
# Instância global
# ---------------------------------------------------------------------------

iris_key_pool = IRISKeyPool()
