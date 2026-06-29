import asyncio

from fastapi import WebSocket

from app.ws.messages import ErrorMessage, StateView, WelcomeMessage


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[int, WebSocket]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def lock(self, code: str) -> asyncio.Lock:
        return self._locks.setdefault(code, asyncio.Lock())

    def attach_player(self, code: str, player_idx: int, websocket: WebSocket) -> None:
        self._rooms.setdefault(code, {})[player_idx] = websocket

    def detach_player(self, code: str, player_idx: int) -> None:
        room_connections = self._rooms.get(code)
        if room_connections and room_connections.get(player_idx) is not None:
            del room_connections[player_idx]

    def connected_player_indices(self, code: str) -> set[int]:
        return set(self._rooms.setdefault(code, {}).keys())

    async def send(self, ws: WebSocket, message: WelcomeMessage | StateView | ErrorMessage) -> None:
        await ws.send_json(message.model_dump(mode="json", by_alias=True))

    async def broadcast(self, code: str, msg: StateView) -> None:
        payload = msg.model_dump(mode="json", by_alias=True)
        for ws in list(self._rooms.get(code, {}).values()):
            await ws.send_json(payload)
