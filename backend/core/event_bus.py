"""
AI Office System - Event Bus
Redis Streams backbone for operational events.

fakeredis is allowed only as an explicit local-development fallback. Health checks
must report it as degraded because events are not durable across restarts.
"""
import asyncio
import json
import logging
from typing import AsyncIterator, Callable, Optional

import redis.asyncio as aioredis

from backend.config.settings import settings
from backend.core.event_types import OfficialEvent
from backend.core.runtime_registry import apply_event_to_registry

logger = logging.getLogger(__name__)

STREAM_KEY = "ai_office:events"
CONSUMER_GROUP = "visual_engine"
WEBSOCKET_CONSUMER = "websocket_bridge"


class EventBus:
    """Redis Streams EventBus with explicit degraded local fallback."""

    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None
        self._subscribers: list[Callable] = []
        self._using_fake = False
        self._mode = "disconnected"

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_persistent(self) -> bool:
        return self._mode == "redis"

    @property
    def is_available(self) -> bool:
        return self._redis is not None

    async def connect(self):
        last_exc: Exception | None = None
        retries = max(1, int(settings.EVENTBUS_REDIS_CONNECT_RETRIES))
        delay = max(0.1, float(settings.EVENTBUS_REDIS_CONNECT_RETRY_DELAY_SECONDS))

        for attempt in range(1, retries + 1):
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
                self._mode = "redis"
                logger.info("EventBus connected to real Redis (%s)", self.redis_url)
                await self._ensure_consumer_group()
                logger.info("EventBus ready. mode=%s persistent=%s", self._mode, self.is_persistent)
                return
            except Exception as exc:
                last_exc = exc
                if attempt < retries:
                    logger.warning(
                        "Real Redis unavailable (%s). retry=%s/%s",
                        exc,
                        attempt,
                        retries,
                    )
                    await asyncio.sleep(delay)

        try:
            raise last_exc or RuntimeError("Redis connection failed")
        except Exception as exc:
            logger.warning("Real Redis unavailable after retries (%s).", exc)
            if not settings.EVENTBUS_ALLOW_FAKE_REDIS:
                self._redis = None
                self._using_fake = False
                self._mode = "offline"
                raise RuntimeError(
                    "Real Redis unavailable and EVENTBUS_ALLOW_FAKE_REDIS=false. "
                    "Start Redis or enable fallback only for development."
                ) from exc

            try:
                import fakeredis.aioredis as fakeredis_aio  # type: ignore

                self._redis = fakeredis_aio.FakeRedis(
                    encoding="utf-8", decode_responses=True
                )
                self._using_fake = True
                self._mode = "fakeredis"
                logger.warning("EventBus using fakeredis: in-memory, not persistent.")
            except ImportError:
                logger.error(
                    "fakeredis is not installed. Install fakeredis[aioredis] or start Redis."
                )
                self._redis = None
                self._using_fake = False
                self._mode = "offline"
                return

        await self._ensure_consumer_group()
        logger.info("EventBus ready. mode=%s persistent=%s", self._mode, self.is_persistent)

    async def disconnect(self):
        if self._redis:
            await self._redis.aclose()
        self._redis = None
        self._mode = "disconnected"

    async def _ensure_consumer_group(self):
        if not self._redis:
            return
        try:
            await self._redis.xgroup_create(
                STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True
            )
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def emit(self, event: OfficialEvent) -> str:
        """Emit an event to the stream and notify in-process subscribers."""
        event_data = event.to_dict()
        apply_event_to_registry(event_data)

        for callback in self._subscribers:
            asyncio.create_task(callback(event_data))

        if not self._redis:
            logger.debug("[EventBus] No Redis; event delivered in-process only.")
            return "0-0"

        msg_id = await self._redis.xadd(STREAM_KEY, {"data": json.dumps(event_data)})
        logger.debug("[EventBus] Emitted %s | id=%s", event.event_type.value, msg_id)
        return msg_id

    def subscribe(self, callback: Callable):
        """Register an in-process realtime subscriber."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        self._subscribers.remove(callback)

    async def read_pending(self, count: int = 100) -> list[dict]:
        """Read new events from the consumer group."""
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
            logger.warning("[EventBus] read_pending failed: %s", exc)
            return []

        events = []
        for _, msgs in messages:
            for msg_id, data in msgs:
                event_data = json.loads(data["data"])
                event_data["_redis_id"] = msg_id
                events.append(event_data)

        return events

    async def ack(self, msg_id: str):
        """Acknowledge a processed stream message."""
        if not self._redis:
            return
        await self._redis.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)

    async def stream_events(self) -> AsyncIterator[dict]:
        """Async generator used by the WebSocket bridge."""
        while True:
            events = await self.read_pending(count=10)
            for event in events:
                yield event
                await self.ack(event["_redis_id"])

            if not events:
                await asyncio.sleep(0.05)

    async def get_history(self, count: int = 500) -> list[dict]:
        """Return recent events for frontend replay on reconnect."""
        if not self._redis:
            return []
        try:
            messages = await self._redis.xrange(STREAM_KEY, count=count)
            return [json.loads(data["data"]) for _, data in messages]
        except Exception as exc:
            logger.warning("[EventBus] get_history failed: %s", exc)
            return []


# Global instance injected into agents and WebSocket code.
event_bus = EventBus(settings.REDIS_URL)
