import secrets

from fastapi import APIRouter, Depends

from app.deps import get_room_store
from app.models import CreateRoomRequest, CreateRoomResponse
from app.store import Player, Room, RoomStore

router = APIRouter(prefix="/rooms")


@router.post("")
async def create_room(
    body: CreateRoomRequest, store: RoomStore = Depends(get_room_store)
) -> CreateRoomResponse:
    code = await store.new_code()
    token = secrets.token_urlsafe(24)
    room = Room(code=code, players=[Player(index=0, display_name=body.display_name, token=token)])
    await store.create(room)
    return CreateRoomResponse(code=code, token=token, player_index=0)
