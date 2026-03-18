"""
api/routes/ws_route.py — WebSocket endpoint.

WS /ws?channels=agents,metrics,alerts&token=<JWT>

Аутентификация через query parameter `token` — WebSocket не поддерживает
Authorization header при handshake. Токен проверяется до accept().
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from api.ws.manager import manager
from services.auth import decode_access_token

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    channels: str = Query("agents,metrics,alerts"),
    token: str = Query(""),
):
    """
    WebSocket соединение.

    channels — comma-separated: agents,metrics,alerts
    token    — JWT access token (обязателен, передаётся как query param)
    """
    # Проверяем JWT до accept() — клиент получит 4001 при отказе
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    payload = decode_access_token(token)
    if not payload:
        await ws.close(code=4001, reason="Invalid or expired token")
        return

    channel_list: List[str] = [c.strip() for c in channels.split(",") if c.strip()]
    if not channel_list:
        channel_list = ["agents", "metrics", "alerts"]

    await manager.connect(ws, channel_list)
    try:
        while True:
            # Держим соединение открытым.
            # Клиент может отправлять ping, мы игнорируем.
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
