import secrets

import redis.asyncio as redis

from app.store.room import Room

_ROOM_TTL_SECONDS = 60 * 60 * 24  # 24h; refreshed on every save (activity)
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
_CODE_LEN = 6


class RoomStore:
    def __init__(self, redis: redis.Redis) -> None:
        self._client = redis

    @staticmethod
    def _key(code: str) -> str:
        return f"room:{code}"

    async def create(self, room: Room) -> bool:
        result = await self._client.set(
            self._key(room.code), room.model_dump_json(), ex=_ROOM_TTL_SECONDS, nx=True
        )
        return result is not None

    async def get(self, code: str) -> Room | None:
        raw = await self._client.get(self._key(code.upper()))
        if raw is None:
            return None
        return Room.model_validate_json(raw)

    async def save(self, room: Room) -> None:
        # refresh TTL on every write so active rooms don't expire mid-game
        await self._client.set(self._key(room.code), room.model_dump_json(), ex=_ROOM_TTL_SECONDS)

    async def new_code(self) -> str:
        for _ in range(10):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))
            if not await self._client.exists(self._key(code)):
                return code
        raise RuntimeError("could not allocate a unique room code")  # ~impossible at hobby scale
