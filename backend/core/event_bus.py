"""
AI Office System — Event Bus
Redis Streams como backbone de eventos.
Producers emitem → Consumers reagem (WebSocket → Frontend).

Fallback automático: se Redis real não estiver disponível, usa fakeredis
(in-memory) para que o sistema rode sem dependência externa durante dev/test.
"""
import asyncio
import json
import logging
from typing import AsyncIterator, Callable, Optional
import redis.asyncio as aioredis

from backend.config.settings import settings
from backend.core.event_types import OfficialEvent, EventType
from backend.core.runtime_registry import apply_event_to_registry

logger = logging.getLogger(__name__)

STREAM_KEY = "ai_office:events"
CONSUMER_GROUP = "visual_engine"
WEBSOCKET_CONSUMER = "websocket_bridge"


class EventBus:
    """
    Event Bus baseado em Redis Streams.
    Fallback automático para fakeredis quando Redis real offline.
    """

    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None
        self._subscribers: list[Callable] = []
        self._using_fake = False

    async def connect(self):
        # 1. Tenta Redis real
        try:
            client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await client.ping()
            self._redis = client
            self._using_fake = False
            logger.info("EventBus conectado ao Redis real (%s)", self.redis_url)
        except Exception as exc:
            logger.warning("Redis real indisponivel (%s) — usando fakeredis in-memory.", exc)
            # 2. Fallback: fakeredis
            try:
                import fakeredis.aioredis as fakeredis_aio  # type: ignore
                self._redis = fakeredis_aio.FakeRedis(
                    encoding="utf-8", decode_responses=True
                )
                self._using_fake = True
                logger.info("EventBus usando fakeredis (in-memory, sem persistencia).")
            except ImportError:
                logger.error(
                    "fakeredis nao instalado. Execute: pip install fakeredis[aioredis]\n"
                    "EventBus rodara sem persistencia (somente pub/sub in-process)."
                )
                self._redis = None
                return
        await self._ensure_consumer_group()
        logger.info("EventBus pronto. fake=%s", self._using_fake)

    async def disconnect(self):
        if self._redis:
            await self._redis.aclose()

    async def _ensure_consumer_group(self):
        try:
            await self._redis.xgroup_create(
                STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True
            )
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def emit(self, event: OfficialEvent) -> str:
        """Emite evento no stream. Retorna o ID gerado pelo Redis."""
        event_data = event.to_dict()
        apply_event_to_registry(event_data)

        # Notifica subscribers in-process (para WebSocket bridge) — sempre
        for callback in self._subscribers:
            asyncio.create_task(callback(event_data))

        if not self._redis:
            logger.debug("[EventBus] Sem Redis — evento entregue apenas in-process.")
            return "0-0"

        msg_id = await self._redis.xadd(STREAM_KEY, {"data": json.dumps(event_data)})
        logger.debug(f"[EventBus] Emitido {event.event_type.value} | id={msg_id}")
        return msg_id

    def subscribe(self, callback: Callable):
        """Registra callback para receber eventos em tempo real (in-process)."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        self._subscribers.remove(callback)

    async def read_pending(self, count: int = 100) -> list[dict]:
        """Lê eventos pendentes (não confirmados) do consumer group."""
        if not self._redis:
            return []

        try:
            messages = await self._redis.xreadgroup(
                CONSUMER_GROUP,
                WEBSOCKET_CONSUMER,
                {STREAM_KEY: ">"},
                count=count,
                block=0,
            )
        except Exception as exc:
            logger.warning("[EventBus] read_pending falhou: %s", exc)
            return []

        events = []
        for _, msgs in messages:
            for msg_id, data in msgs:
                event_data = json.loads(data["data"])
                event_data["_redis_id"] = msg_id
                events.append(event_data)

        return events

    async def ack(self, msg_id: str):
        """Confirma processamento de mensagem."""
        await self._redis.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)

    async def stream_events(self) -> AsyncIterator[dict]:
        """
        Generator assíncrono — itera eventos em tempo real.
        Usado pelo WebSocket bridge.
        """
        while True:
            events = await self.read_pending(count=10)
            for event in events:
                yield event
                await self.ack(event["_redis_id"])

            if not events:
                await asyncio.sleep(0.05)  # 50ms polling — leve e responsivo

    async def get_history(self, count: int = 500) -> list[dict]:
        """Retorna histórico de eventos para replay no frontend ao conectar."""
        if not self._redis:
            return []
        try:
            messages = await self._redis.xrange(STREAM_KEY, count=count)
            return [json.loads(data["data"]) for _, data in messages]
        except Exception as exc:
            logger.warning("[EventBus] get_history falhou: %s", exc)
            return []


# Instância global — injetada nos agentes e WebSocket
event_bus = EventBus(settings.REDIS_URL)
