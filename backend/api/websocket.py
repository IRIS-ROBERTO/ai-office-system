"""
AI Office System — WebSocket Bridge
Ponte em tempo real entre o EventBus e o frontend.
Gerencia múltiplas conexões, replay de histórico e heartbeat.
"""
import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect

from backend.core.event_bus import event_bus

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gerencia o conjunto de WebSockets ativos e distribui eventos."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(
            f"[WS] Cliente conectado. Total: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(
            f"[WS] Cliente desconectado. Total: {len(self.active_connections)}"
        )

    async def send_json(self, websocket: WebSocket, data: dict):
        """Envia payload JSON para uma conexão específica."""
        try:
            await websocket.send_text(json.dumps(data))
        except Exception as e:
            logger.warning(f"[WS] Falha ao enviar para cliente: {e}")
            self.disconnect(websocket)

    async def broadcast(self, data: dict):
        """Distribui evento para todos os clientes conectados."""
        dead: set[WebSocket] = set()
        for ws in list(self.active_connections):
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws)


# Instância global — compartilhada por todas as rotas WS
manager = ConnectionManager()


async def _heartbeat(websocket: WebSocket, interval: int = 30):
    """Envia ping a cada `interval` segundos para manter a conexão viva."""
    while True:
        await asyncio.sleep(interval)
        try:
            await websocket.send_text(json.dumps({"type": "heartbeat"}))
        except Exception:
            break


async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket principal — /ws
    1. Aceita conexão e envia histórico para sincronização.
    2. Subscribe no EventBus para eventos em tempo real.
    3. Mantém heartbeat a cada 30s.
    4. Ao desconectar: unsubscribe e remove da pool.
    """
    await manager.connect(websocket)

    # --- Replay: envia histórico para o cliente recém-conectado ---
    try:
        history = await event_bus.get_history(count=500)
        await manager.send_json(
            websocket,
            {
                "type": "history",
                "events": history,
                "total": len(history),
            },
        )
    except Exception as e:
        logger.warning(f"[WS] Não foi possível enviar histórico: {e}")

    # --- Callback: distribuir novos eventos para TODOS os clientes ---
    async def on_event(event_data: dict):
        await manager.broadcast({"type": "event", "data": event_data})

    event_bus.subscribe(on_event)

    # --- Heartbeat em background ---
    heartbeat_task = asyncio.create_task(_heartbeat(websocket, interval=30))

    try:
        # Mantém a conexão aberta aguardando mensagens do cliente
        # (o cliente pode enviar pings ou comandos futuros)
        while True:
            try:
                data = await websocket.receive_text()
                # Echo de ping customizado caso o cliente envie
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.debug(f"[WS] receive_text erro: {e}")
                break
    finally:
        heartbeat_task.cancel()
        event_bus.unsubscribe(on_event)
        manager.disconnect(websocket)
