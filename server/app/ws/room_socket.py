import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from app.engine import ActorMove, InProgress, Move, MovieMove, forfeit, play_move
from app.store import (
    ActorMoveModel,
    Player,
    Room,
    RoomStore,
    apply_game_over,
    apply_in_progress,
    to_engine_state,
)
from app.tmdb_client import TmdbClient
from app.ws.manager import ConnectionManager
from app.ws.messages import (
    ClientMessage,
    ErrorMessage,
    ForfeitMessage,
    JoinMessage,
    PlayerView,
    ResumeMessage,
    StateView,
    SubmitMoveMessage,
    WelcomeMessage,
)

router = APIRouter()
_client_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def _state_view(room: Room, manager: ConnectionManager) -> StateView:
    connected = manager.connected_player_indices(room.code)
    return StateView(
        code=room.code,
        phase=room.phase,
        players=[
            PlayerView(index=p.index, display_name=p.display_name, connected=p.index in connected)
            for p in room.players
        ],
        moves=room.moves,
        current_player_index=room.current_player_index,
        winner_index=room.winner_index,
        losing_move=room.losing_move,
    )


@router.websocket("/ws/rooms/{code}")
async def room_socket(ws: WebSocket, code: str) -> None:
    code = code.upper()
    store: RoomStore = ws.app.state.room_store
    manager: ConnectionManager = ws.app.state.connection_manager
    tmdb: TmdbClient = ws.app.state.tmdb_client

    await ws.accept()

    # 1) Authenticate via the first frame (join or resume).
    player_index = await _authenticate(ws, code, store, manager)
    if player_index is None:
        await ws.close()
        return

    try:
        while True:
            raw = await ws.receive_json()
            await _handle_frame(ws, code, player_index, raw, store, manager, tmdb)
    except WebSocketDisconnect:
        manager.detach_player(code, player_index)
        # broadcast updated connected-flags so the peer sees the drop
        room = await store.get(code)
        if room is not None:
            await manager.broadcast(code, _state_view(room, manager))


async def _authenticate(
    ws: WebSocket, code: str, store: RoomStore, manager: ConnectionManager
) -> int | None:
    raw = await ws.receive_json()
    try:
        msg = _client_adapter.validate_python(raw)
    except ValidationError:
        await manager.send(ws, ErrorMessage(message="malformed message", code="bad_message"))
        return None

    async with manager.lock(code):
        room = await store.get(code)
        if room is None:
            await manager.send(ws, ErrorMessage(message="no such room", code="bad_token"))
            return None

        if isinstance(msg, ResumeMessage):
            player = next((p for p in room.players if p.token == msg.token), None)
            if player is None:
                await manager.send(ws, ErrorMessage(message="invalid token", code="bad_token"))
                return None
            idx, token_out = player.index, None
        elif isinstance(msg, JoinMessage):
            if len(room.players) >= room.player_count:
                await manager.send(ws, ErrorMessage(message="room is full", code="room_full"))
                return None
            idx = len(room.players)
            token_out = secrets.token_urlsafe(24)
            room.players.append(Player(index=idx, display_name=msg.display_name, token=token_out))
            if len(room.players) == room.player_count and room.started_at is None:
                from datetime import UTC, datetime

                room.started_at = datetime.now(UTC)
            await store.save(room)
        else:
            await manager.send(ws, ErrorMessage(message="join or resume first", code="bad_message"))
            return None

        manager.attach_player(code, idx, ws)
        await manager.send(
            ws, WelcomeMessage(player_index=idx, token=token_out, state=_state_view(room, manager))
        )
        await manager.broadcast(code, _state_view(room, manager))
        return idx


async def _handle_frame(
    ws: WebSocket,
    code: str,
    player_index: int,
    raw: str,
    store: RoomStore,
    manager: ConnectionManager,
    tmdb: TmdbClient,
) -> None:
    try:
        msg = _client_adapter.validate_python(raw)
    except ValidationError:
        await manager.send(ws, ErrorMessage(message="malformed message", code="bad_message"))
        return

    async with manager.lock(code):
        room = await store.get(code)
        if room is None or room.phase != "playing":
            await manager.send(ws, ErrorMessage(message="game not in progress", code="bad_message"))
            return
        if player_index != room.current_player_index:
            await manager.send(ws, ErrorMessage(message="not your turn", code="not_your_turn"))
            return

        state = to_engine_state(room)
        if isinstance(msg, SubmitMoveMessage):
            move = await _build_move(msg, tmdb)
            result = play_move(state, move)
        elif isinstance(msg, ForfeitMessage):
            result = forfeit(state)
        else:
            await manager.send(ws, ErrorMessage(message="unexpected message", code="bad_message"))
            return

        if isinstance(result, InProgress):
            room = apply_in_progress(room, result)
            await store.save(room)
        else:  # GameOver
            room = apply_game_over(room, result)
            await store.save(room)

        await manager.broadcast(code, _state_view(room, manager))


async def _build_move(msg: SubmitMoveMessage, tmdb: TmdbClient) -> Move:
    m = msg.move
    if isinstance(m, ActorMoveModel):
        return ActorMove(id=m.id, display_text=m.display_text, image_path=m.image_path)
    # D1: re-fetch authoritative cast; ignore any client-sent cast_ids.
    credits = await tmdb.get_movie_credits(m.id)
    return MovieMove(
        id=m.id,
        display_text=m.display_text,
        cast_ids=set(credits.cast_ids),
        release_year=m.release_year,
    )
