"""
AI Office System — Event Bus
Redis Streams como backbone de eventos.
Producers emitem → Consumers reagem (WebSocket → Frontend).
"""
import asyncio
import json
import logging
from typing import AsyncIterator, Callable, Optional
import redis.asyncio as aioredis

from backend.core.event_types import OfficialEvent, EventType

logger = logging.getLogger(__name__)

STREAM_KEY = "ai_office:events"
CONSUMER_GROUP = "visual_engine"
WEBSOCKET_CONSUMER = "websocket_bridge"


class EventBus:
    """
    Event Bus baseado em Redis Streams.
    Garante persistência, replay e consumer groups.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None
        self._subscribers: list[Callable] = []

    async def connect(self):
        self._redis = await aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await self._ensure_consumer_group()
        logger.info("EventBus conectado ao Redis")

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
        if not self._redis:
            raise RuntimeError("EventBus não conectado")

        event_data = event.to_dict()
        msg_id = await self._redis.xadd(STREAM_KEY, {"data": json.dumps(event_data)})
        logger.debug(f"[EventBus] Emitido {event.event_type.value} | id={msg_id}")

        # Notifica subscribers in-process (para WebSocket bridge)
        for callback in self._subscribers:
            asyncio.create_task(callback(event_data))

        return msg_id

    def subscribe(self, callback: Callable):
        """Registra callback para receber eventos em tempo real (in-process)."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        self._subscribers.remove(callback)

    async def read_pending(self, count: int = 100) -> list[dict]:
        """Lê eventos pendentes (não confirmados) do consumer group."""
        if not self._redis:
            raise RuntimeError("EventBus não conectado")

        messages = await self._redis.xreadgroup(
            CONSUMER_GROUP,
            WEBSOCKET_CONSUMER,
            {STREAM_KEY: ">"},
            count=count,
            block=0,
        )

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
        messages = await self._redis.xrange(STREAM_KEY, count=count)
        return [json.loads(data["data"]) for _, data in messages]


# Instância global — injetada nos agentes e WebSocket
event_bus = EventBus()
