"""
api/ws/manager.py — менеджер WebSocket соединений.

Клиенты подписываются на каналы: 'agents' | 'metrics' | 'alerts'.
Broadcaster пушит только дельты.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # channel → set of websockets
        self._connections: Dict[str, Set[WebSocket]] = {
            "agents":  set(),
            "metrics": set(),
            "alerts":  set(),
        }
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, channels: List[str]) -> None:
        await ws.accept()
        async with self._lock:
            for ch in channels:
                if ch in self._connections:
                    self._connections[ch].add(ws)
        logger.debug("[WS] Подключён клиент, каналы: %s", channels)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            for ch in self._connections:
                self._connections[ch].discard(ws)
        logger.debug("[WS] Отключён клиент")

    async def broadcast(self, channel: str, data: dict) -> None:
        """Рассылает сообщение всем подписчикам канала."""
        message = {"channel": channel, "data": data}
        if channel not in self._connections:
            return

        async with self._lock:
            targets = list(self._connections[channel])

        dead: List[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        # Убираем мёртвые соединения
        if dead:
            async with self._lock:
                for ws in dead:
                    for ch in self._connections:
                        self._connections[ch].discard(ws)


# Глобальный singleton
manager = ConnectionManager()
