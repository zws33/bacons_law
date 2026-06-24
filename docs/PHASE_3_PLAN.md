# Phase 3 Implementation Plan — Multiplayer Session Layer

Source of scope: [PYTHON_TS_REWRITE_PLAN.md](PYTHON_TS_REWRITE_PLAN.md#phase-3-multiplayer-session-layer)
Engine contract (authoritative): [GAME_SPEC_V2.md](GAME_SPEC_V2.md)
Builds on: [PHASE_1_PLAN.md](PHASE_1_PLAN.md) (engine), [PHASE_2_PLAN.md](PHASE_2_PLAN.md) (TMDB proxy, DI, `TmdbClient`)

**Done when:** two separate WebSocket clients (e.g. two browser tabs) can complete a full game with every move validated **server-side** by the Phase 1 engine, a disconnected client can reconnect with its token and receive a fresh snapshot, and each completed game (win or forfeit) writes exactly one row to Postgres. `mypy --strict`, `ruff`, and `pytest` are clean, with no real Redis/Postgres/TMDB calls in tests.

**Audience:** Senior engineer fluent in TypeScript/Kotlin, newer to Python's async ecosystem. New runtime concepts (FastAPI WebSockets, `redis.asyncio`, SQLAlchemy 2.0 async, Alembic, Pydantic discriminated unions) are explained where they diverge from the JVM/Node equivalents.

---

## What we're building

Phase 1 gave us a pure engine. Phase 2 gave us a stateless TMDB proxy. Phase 3 is the first **stateful** layer — it owns live game sessions and the durable record of finished games. This is the largest phase by surface area and the one with the most new infrastructure.

The shape of the work:

- **`POST /rooms`** — create a room, reserve the creator as player 0, return a room code + an opaque creator token.
- **`WS /ws/rooms/{code}`** — the live channel. A connection authenticates (join as a new player, or resume with an existing token), submits moves and forfeits, and receives state broadcasts. All `GameState` transitions happen here, delegated to the Phase 1 engine.
- **Redis** — the only home of live `GameState` while a game is in progress, keyed by room code, TTL'd so abandoned rooms expire.
- **Postgres** — written exactly once per game, at `GameOver`, with the full chain, players, winner, and timestamps. Never read during play.

The architectural inversion from the Kotlin project (DECISIONS 007) lands here: the **server** is now the authoritative state owner. The client renders state it receives; it never runs the engine and never decides the outcome of a move.

---

## Concepts: what's new this phase

### FastAPI WebSocket endpoints

A WebSocket route is declared with `@router.websocket(...)` instead of `@router.get(...)`. The handler receives a `WebSocket` object, calls `await ws.accept()`, then loops on `await ws.receive_json()` until the client disconnects (which raises `WebSocketDisconnect`).

```python
@router.websocket("/ws/rooms/{code}")
async def room_socket(ws: WebSocket, code: str) -> None:
    await ws.accept()
    try:
        while True:
            payload = await ws.receive_json()
            ...  # dispatch on payload["type"]
    except WebSocketDisconnect:
        ...  # cleanup
```

There is no request/response cycle — it's a long-lived bidirectional stream. This is exactly the property that ruled out scale-to-zero hosting (PYTHON_TS_REWRITE_PLAN, "Realtime transport" decision). For a Kotlin engineer: this is Ktor's `webSocket("/path") { for (frame in incoming) { ... } }`. For Node: `ws.on("message", ...)`.

### `redis.asyncio` — async Redis client

`redis-py` ships an async client at `redis.asyncio`. It is `await`-native and connection-pooled. We use it as a typed key/value store: one JSON blob per room.

```python
import redis.asyncio as redis

pool = redis.Redis.from_url(url)           # created once in the lifespan
await pool.set(f"room:{code}", blob, ex=TTL)   # ex = TTL seconds, refreshed on each write
raw = await pool.get(f"room:{code}")       # bytes | None
```

We do not use Redis pub/sub in v1 — broadcasting is in-process (see D6). Redis is purely the durable-across-reconnect state store, not the message bus.

### SQLAlchemy 2.0 async + Alembic

SQLAlchemy 2.0's async API (`create_async_engine`, `async_sessionmaker`, `AsyncSession`) is the standard way to talk to Postgres from FastAPI. The driver is `asyncpg`. Alembic is the migration tool — the Python equivalent of Flyway/Liquibase in the JVM world, or Prisma Migrate in Node. We define one ORM model (`GameRecord`) and one migration that creates its table.

| Kotlin/JVM | Python |
| --- | --- |
| Exposed / JPA entity | SQLAlchemy `DeclarativeBase` model |
| Flyway migration SQL | Alembic `versions/*.py` |
| HikariCP pool | `create_async_engine(...)` pool |
| `Database.connect()` | `async_sessionmaker(engine)()` |

### Pydantic discriminated unions

The WS protocol is a tagged union of message types. Pydantic v2 models this natively with a `type` discriminator field, so a single `model_validate` call parses an incoming frame into the correct concrete type and rejects unknown ones:

```python
ClientMessage = Annotated[
    JoinMessage | ResumeMessage | SubmitMoveMessage | ForfeitMessage,
    Field(discriminator="type"),
]
```

This is the wire-protocol analogue of the engine's `Move = ActorMove | MovieMove` union (Phase 1), but here Pydantic *does* enforce exhaustiveness at parse time because the discriminator is explicit. For a TS engineer this is a discriminated union on a `type` literal field; Pydantic does the `switch (msg.type)` narrowing for you.

### Per-room `asyncio.Lock`

Two frames for the same room could interleave between the Redis read and the Redis write (read-modify-write race). Because v1 is single-instance (D6), a per-room `asyncio.Lock` held across the read→engine→write critical section fully serializes handling. Multi-instance would need Redis `WATCH`/`MULTI` or a Lua script — explicitly deferred (PYTHON_TS_REWRITE_PLAN, "out of scope").

---

## Design decisions

These set contracts that Phase 4's client depends on. The WS message protocol and the `POST /rooms` shape are **one-way doors** once the client is built against them.

### D1 — Server is authoritative; the client never sends `cast_ids`

A `submit_move` frame carries only what the client knows: `kind` (`"actor"`/`"movie"`), `id`, `display_text`, and (for movies) `release_year`. It does **not** carry `cast_ids`. For a movie move, the **server** fetches credits via the Phase 2 `TmdbClient.get_movie_credits(id)` and builds the `MovieMove` with the authoritative cast. For an actor move, the server builds the `ActorMove` directly.

**Trade-off:** one extra TMDB round-trip per movie move (cost) versus a client that cannot forge a connection by sending a fabricated cast list (benefit). For a server-authoritative design this is non-negotiable — trusting client-sent `cast_ids` would make validation theater. This is the session-layer mapping the Phase 2 plan foreshadowed (`MovieCreditsResult` → engine `MovieMove`, converting `list[int]` → `set[int]` at this boundary).

### D2 — Two auth paths over one symmetric protocol: `join` and `resume`

Every WS connection's **first frame** authenticates it. There is no token in the query string (browser `WebSocket` can't set headers, and tokens in URLs leak into logs).

- `join` `{display_name}` — a new player with no token. Server allocates the next free player slot, issues a token, replies `welcome` carrying the token (client persists it).
- `resume` `{token}` — a known player (the creator from `POST /rooms`, or any player reconnecting). Server validates the token against the room's player list, replies `welcome` (no new token).

The creator always `resume`s with their `POST /rooms` token. A second player always `join`s. A reconnecting player `resume`s. One protocol, two entry messages — symmetric and no query-string secrets.

### D3 — A "repeat detection ends the game" move is **not** a protocol error

Critical distinction the protocol must preserve. An **invalid move** (bad connection, repeat, wrong type) is a legitimate game event — it ends the game per R6, and the server responds by broadcasting a `state` with phase `over`. A **protocol error** (submitting when it's not your turn, malformed frame, bad token, room full) is answered with an `error` frame sent only to the offender and does **not** mutate game state. Conflating these would let a player end the game by spamming out-of-turn moves.

"Not your turn" is enforced by the session layer (compare the sender's `player_index` to `current_player_index`) **before** calling the engine — the engine has no concept of connection identity.

### D4 — Room model lives in the session layer; engine stays pure

`GameState` (engine) has no concept of player names, tokens, room codes, or connection status. Those are session concerns. A `Room` Pydantic model wraps the engine state with that metadata, exactly as the Kotlin `GameSession` wrapped `GameState` with `playerNames` (GAME_REPOSITORY_REFACTOR, Step 3). The engine still receives and returns bare `InProgress`/`GameOver`; the session layer maps in and out at the Redis boundary.

### D5 — Persist the whole `Room` as one JSON blob; project a token-free `StateView` for clients

Redis holds `room.model_dump_json()` under `room:{code}` — one atomic value, including tokens (Redis is server-side only). What gets **broadcast** is a separate `StateView` projection that excludes tokens and adds per-player `connected` flags (sourced from the in-process `ConnectionManager`, not from Redis). One model persisted, a different model on the wire — the same split as Phase 2's engine-vs-API model layers.

### D6 — Single-instance v1: in-process `ConnectionManager`, per-room `asyncio.Lock`

Live WebSocket objects can't be serialized to Redis, so the registry of "who is connected to which room" is an in-process dict (`code → {player_index: WebSocket}`). Broadcasting iterates that dict. This means v1 runs as a single backend instance — consistent with the master plan's explicit deferral of multi-instance scaling. The per-room lock (held across read-modify-write) makes concurrent frames safe within that instance. The scale path (Redis pub/sub fan-out + distributed lock) is noted in Risk flags, not built.

### D7 — Postgres write is fire-once at `GameOver`, inside the same critical section

When `play_move`/`forfeit` returns `GameOver`, the handler — still holding the room lock — saves the terminal room to Redis, writes one `GameRecord` row, then broadcasts. The write uses the room's `started_at`/`ended_at`. Because the room transitions to `over` exactly once (subsequent moves are rejected: the state is no longer `InProgress`), the row is written exactly once. No dedup logic needed.

### D8 — History **read** endpoints (`GET /games`, `GET /games/{id}`) are deferred to Phase 4

Phase 3 builds the schema, the migration, and the write path. The read endpoints are built in Phase 4 alongside the history UI that consumes them — no point shipping an endpoint with no caller a phase early. The `games` table and its `GameRecord` model are the stable contract those endpoints will read.

### D9 — Room codes: 6-char uppercase base32, collision-retried

Human-typable (phone-to-phone, read aloud), case-insensitive on input. Generated from `secrets.choice` over an unambiguous alphabet (no `0/O`, `1/I`). On the rare Redis-key collision, retry. Codes are not secrets — the **token** is the capability; the code is just an address.

---

## Target file layout

```
server/app/
├── api/
│   ├── __init__.py          # update: include rooms_router
│   └── rooms.py             # NEW: POST /rooms
├── ws/
│   ├── __init__.py          # update: export ws_router
│   ├── messages.py          # NEW: Pydantic client/server WS message models
│   ├── manager.py           # NEW: ConnectionManager (in-process registry + broadcast)
│   └── room_socket.py       # NEW: /ws/rooms/{code} endpoint + frame dispatch
├── store/
│   ├── __init__.py          # update: re-exports
│   ├── room.py              # NEW: Room, Player, MoveModel (Pydantic) + engine mapping
│   ├── room_store.py        # NEW: RoomStore (redis.asyncio CRUD, TTL, code generation)
│   ├── db.py                # NEW: async engine + session factory
│   ├── db_models.py         # NEW: SQLAlchemy GameRecord ORM model + Base
│   └── history.py           # NEW: write_completed_game(session, room)
├── models/
│   └── room.py              # NEW: CreateRoomRequest, CreateRoomResponse (REST DTOs)
├── deps.py                  # update: get_room_store, get_db_session, get_connection_manager
└── main.py                  # update: lifespan opens redis + db, mounts ws_router

server/
├── alembic.ini              # NEW
└── migrations/
    ├── env.py               # NEW (async template)
    ├── script.py.mako       # NEW (alembic-generated)
    └── versions/
        └── 0001_create_games_table.py   # NEW

server/tests/
├── conftest.py              # update: REDIS_URL/DATABASE_URL placeholders
└── session/
    ├── __init__.py          # NEW
    ├── conftest.py          # NEW: fakeredis + sqlite session + FakeTmdbClient wiring
    ├── test_rooms.py        # NEW: POST /rooms
    ├── test_gameplay.py     # NEW: full game over WS, invalid move, forfeit
    ├── test_reconnect.py    # NEW: resume with token, bad token, room full
    └── test_history.py      # NEW: GameOver writes a row
```

`pyproject.toml` additions:
- prod: `redis>=5.2.0`, `sqlalchemy>=2.0.36`, `asyncpg>=0.30.0`, `alembic>=1.14.0`
- dev: `fakeredis>=2.26.0`, `aiosqlite>=0.20.0`

---

## File-by-file

### `server/app/store/room.py` — domain model + engine mapping

The Pydantic `Room` is the persisted/working session model. `to_engine_state` / `from_engine_state` are the mapping layer between it and the pure engine.

```python
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.engine import ActorMove, GameOver, InProgress, Move, MovieMove


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ActorMoveModel(_CamelModel):
    kind: Literal["actor"] = "actor"
    id: int
    display_text: str
    image_path: str | None = None


class MovieMoveModel(_CamelModel):
    kind: Literal["movie"] = "movie"
    id: int
    display_text: str
    cast_ids: set[int] = Field(default_factory=set)
    image_path: str | None = None
    release_year: str | None = None


MoveModel = Annotated[ActorMoveModel | MovieMoveModel, Field(discriminator="kind")]


class Player(_CamelModel):
    index: int
    display_name: str
    token: str          # never sent to other clients; excluded from StateView


class Room(_CamelModel):
    code: str
    players: list[Player] = Field(default_factory=list)
    moves: list[MoveModel] = Field(default_factory=list)
    current_player_index: int = 0
    player_count: int = 2
    # terminal fields, populated on GameOver:
    winner_index: int | None = None
    losing_move: MoveModel | None = None
    # lifecycle timestamps:
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    ended_at: datetime | None = None

    @property
    def phase(self) -> Literal["waiting", "playing", "over"]:
        if self.ended_at is not None:
            return "over"
        if len(self.players) < self.player_count:
            return "waiting"
        return "playing"


# --- engine <-> model mapping -------------------------------------------

def _model_to_move(m: MoveModel) -> Move:
    if m.kind == "actor":
        return ActorMove(id=m.id, display_text=m.display_text, image_path=m.image_path)
    return MovieMove(
        id=m.id,
        display_text=m.display_text,
        cast_ids=set(m.cast_ids),
        image_path=m.image_path,
        release_year=m.release_year,
    )


def _move_to_model(m: Move) -> MoveModel:
    if isinstance(m, ActorMove):
        return ActorMoveModel(id=m.id, display_text=m.display_text, image_path=m.image_path)
    return MovieMoveModel(
        id=m.id,
        display_text=m.display_text,
        cast_ids=m.cast_ids,
        image_path=m.image_path,
        release_year=m.release_year,
    )


def to_engine_state(room: Room) -> InProgress:
    return InProgress(
        moves=[_model_to_move(m) for m in room.moves],
        current_player_index=room.current_player_index,
        player_count=room.player_count,
    )


def apply_in_progress(room: Room, state: InProgress) -> Room:
    return room.model_copy(
        update={
            "moves": [_move_to_model(m) for m in state.moves],
            "current_player_index": state.current_player_index,
        }
    )


def apply_game_over(room: Room, state: GameOver) -> Room:
    return room.model_copy(
        update={
            "winner_index": state.winner_index,
            "losing_move": _move_to_model(state.losing_move) if state.losing_move else None,
            "ended_at": datetime.now(UTC),
        }
    )
```

Notes:
- `MoveModel`'s `kind` discriminator is the persistence/wire equivalent of `isinstance` on the engine union. Pydantic parses the right subtype from stored JSON and rejects unknown kinds.
- `cast_ids: set[int]` round-trips cleanly: Pydantic serializes a set to a JSON array and parses it back to a set on load, so the engine's `set[int]` contract holds end-to-end without manual conversion.
- `phase` is **derived**, not stored — fewer invariants to keep consistent (D4 rationale, same as the Kotlin `GameSession`'s `null = not started`).
- `model_copy(update=...)` produces a new `Room` (immutable-update style), mirroring the engine's pure transitions.

### `server/app/store/room_store.py` — Redis CRUD

```python
import secrets

import redis.asyncio as redis

from app.store.room import Room

_ROOM_TTL_SECONDS = 60 * 60 * 24  # 24h; refreshed on every save (activity)
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
_CODE_LEN = 6


class RoomStore:
    def __init__(self, client: redis.Redis) -> None:
        self._redis = client

    @staticmethod
    def _key(code: str) -> str:
        return f"room:{code}"

    async def create(self, room: Room) -> None:
        await self._redis.set(self._key(room.code), room.model_dump_json(), ex=_ROOM_TTL_SECONDS)

    async def get(self, code: str) -> Room | None:
        raw = await self._redis.get(self._key(code.upper()))
        if raw is None:
            return None
        return Room.model_validate_json(raw)

    async def save(self, room: Room) -> None:
        # refresh TTL on every write so active rooms don't expire mid-game
        await self._redis.set(self._key(room.code), room.model_dump_json(), ex=_ROOM_TTL_SECONDS)

    async def new_code(self) -> str:
        for _ in range(10):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))
            if not await self._redis.exists(self._key(code)):
                return code
        raise RuntimeError("could not allocate a unique room code")  # ~impossible at hobby scale
```

Notes:
- `model_dump_json()` / `model_validate_json()` are the only serialization surface — no hand-written serde. Sets, optionals, nested unions all handled by Pydantic.
- `get` upper-cases the code so client input is case-insensitive (D9).
- TTL is set on every `create`/`save` (`ex=`), so a room only expires after 24h of no activity.

### `server/app/store/db.py` and `db_models.py` — Postgres

```python
# db_models.py
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GameRecord(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_code: Mapped[str] = mapped_column(String(16), nullable=False)
    player_names: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    winner_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chain: Mapped[list[dict]] = mapped_column(JSON, nullable=False)        # serialized MoveModels
    losing_move: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # None on forfeit
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

```python
# db.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def make_engine(url: str):  # url: postgresql+asyncpg://...  (sqlite+aiosqlite://... in tests)
    return create_async_engine(url, future=True)


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
```

Notes:
- `JSON` columns store the `MoveModel`/name lists directly — Postgres maps `JSON` to `jsonb`-compatible `json`; SQLite (tests) stores text. We never query *inside* the chain, so a typed relational move table would be over-engineering (history is read whole, by id).
- `expire_on_commit=False` keeps attributes accessible after commit without a reload — standard for the write-and-discard pattern here.

### `server/app/store/history.py` — the one-shot archival write

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.store.db_models import GameRecord
from app.store.room import Room


async def write_completed_game(session: AsyncSession, room: Room) -> None:
    assert room.winner_index is not None and room.started_at and room.ended_at
    record = GameRecord(
        room_code=room.code,
        player_names=[p.display_name for p in room.players],
        winner_index=room.winner_index,
        chain=[m.model_dump(by_alias=True) for m in room.moves],
        losing_move=room.losing_move.model_dump(by_alias=True) if room.losing_move else None,
        started_at=room.started_at,
        ended_at=room.ended_at,
    )
    session.add(record)
    await session.commit()
```

`by_alias=True` serializes the stored JSON in camelCase, matching what Phase 4's history detail endpoint will return.

### `server/app/ws/messages.py` — the wire protocol

```python
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.store.room import MoveModel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# --- client -> server ----------------------------------------------------

class JoinMessage(_CamelModel):
    type: Literal["join"] = "join"
    display_name: str


class ResumeMessage(_CamelModel):
    type: Literal["resume"] = "resume"
    token: str


class SubmitMoveMessage(_CamelModel):
    type: Literal["submit_move"] = "submit_move"
    move: MoveModel        # cast_ids is ignored if a client sends it; server re-fetches (D1)


class ForfeitMessage(_CamelModel):
    type: Literal["forfeit"] = "forfeit"


ClientMessage = Annotated[
    JoinMessage | ResumeMessage | SubmitMoveMessage | ForfeitMessage,
    Field(discriminator="type"),
]


# --- server -> client ----------------------------------------------------

class PlayerView(_CamelModel):
    index: int
    display_name: str
    connected: bool


class StateView(_CamelModel):
    type: Literal["state"] = "state"
    code: str
    phase: Literal["waiting", "playing", "over"]
    players: list[PlayerView]
    moves: list[MoveModel]
    current_player_index: int
    winner_index: int | None = None
    losing_move: MoveModel | None = None


class WelcomeMessage(_CamelModel):
    type: Literal["welcome"] = "welcome"
    player_index: int
    token: str | None = None     # present only for a fresh `join`
    state: StateView


class ErrorMessage(_CamelModel):
    type: Literal["error"] = "error"
    message: str
    code: str       # machine-readable: "not_your_turn" | "room_full" | "bad_token" | "bad_message"
```

Notes:
- `SubmitMoveMessage.move` reuses `MoveModel`, but the handler **discards** any client-sent `cast_ids` for movie moves and re-fetches (D1). Reusing the type keeps one move schema across persistence and wire.
- `StateView` is the token-free projection (D5). `PlayerView.connected` is filled from the `ConnectionManager`, not from `Room`.

### `server/app/ws/manager.py` — in-process registry

```python
import asyncio

from fastapi import WebSocket

from app.ws.messages import ErrorMessage, StateView, WelcomeMessage


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[int, WebSocket]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def lock(self, code: str) -> asyncio.Lock:
        return self._locks.setdefault(code, asyncio.Lock())

    def attach(self, code: str, player_index: int, ws: WebSocket) -> None:
        self._rooms.setdefault(code, {})[player_index] = ws

    def detach(self, code: str, player_index: int) -> None:
        conns = self._rooms.get(code)
        if conns and conns.get(player_index) is not None:
            del conns[player_index]

    def connected_indices(self, code: str) -> set[int]:
        return set(self._rooms.get(code, {}).keys())

    async def send(self, ws: WebSocket, msg: WelcomeMessage | StateView | ErrorMessage) -> None:
        await ws.send_json(msg.model_dump(by_alias=True))

    async def broadcast(self, code: str, msg: StateView) -> None:
        for ws in list(self._rooms.get(code, {}).values()):
            await ws.send_json(msg.model_dump(by_alias=True))
```

Notes:
- `connected_indices` feeds `PlayerView.connected`. A player can exist in `Room.players` (joined, has a token) but be absent here (disconnected) — exactly the reconnect case.
- A single connection per `player_index`: a `resume` from a second tab replaces the first (last-writer-wins). v1 doesn't fan out to multiple devices per player.
- `model_dump(by_alias=True)` emits camelCase on the wire.

### `server/app/ws/room_socket.py` — the handler

This is the heart of the phase. It dispatches frames, enforces D3's protocol-error vs. game-event split, and holds the per-room lock across each state mutation.

```python
import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.engine import GameOver, InProgress, play_move, forfeit
from app.store.history import write_completed_game
from app.store.room import (
    ActorMoveModel,
    MovieMoveModel,
    Player,
    Room,
    apply_game_over,
    apply_in_progress,
    to_engine_state,
)
from app.store.room_store import RoomStore
from app.tmdb_client import TmdbClient
from app.ws.manager import ConnectionManager
from app.ws.messages import (
    ClientMessage,
    ErrorMessage,
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
    connected = manager.connected_indices(room.code)
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
    session_factory: async_sessionmaker = ws.app.state.session_factory

    await ws.accept()

    # 1) Authenticate via the first frame (join or resume).
    player_index = await _authenticate(ws, code, store, manager)
    if player_index is None:
        await ws.close()
        return

    try:
        while True:
            raw = await ws.receive_json()
            await _handle_frame(ws, code, player_index, raw, store, manager, tmdb, session_factory)
    except WebSocketDisconnect:
        manager.detach(code, player_index)
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

        manager.attach(code, idx, ws)
        await manager.send(
            ws, WelcomeMessage(player_index=idx, token=token_out, state=_state_view(room, manager))
        )
        await manager.broadcast(code, _state_view(room, manager))
        return idx


async def _handle_frame(
    ws, code, player_index, raw, store, manager, tmdb, session_factory
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
            async with session_factory() as session:
                await write_completed_game(session, room)

        await manager.broadcast(code, _state_view(room, manager))


async def _build_move(msg: SubmitMoveMessage, tmdb: TmdbClient):
    m = msg.move
    if isinstance(m, ActorMoveModel):
        from app.engine import ActorMove
        return ActorMove(id=m.id, display_text=m.display_text, image_path=m.image_path)
    # D1: re-fetch authoritative cast; ignore any client-sent cast_ids.
    from app.engine import MovieMove
    credits = await tmdb.get_movie_credits(m.id)
    return MovieMove(
        id=m.id,
        display_text=m.display_text,
        cast_ids=set(credits.cast_ids),
        release_year=m.release_year,
    )
```

Notes:
- The lock is held across `get → engine → save → (history) → broadcast` so no two frames for the same room interleave (D6). The TMDB fetch in `_build_move` happens **inside** the lock — acceptable for a 2-player turn-based game where at most one move is in flight; the alternative (fetch before locking) reintroduces a stale-read window.
- Protocol errors (`not_your_turn`, `room_full`, `bad_token`, `bad_message`) reply only to `ws` and never touch state (D3). A losing move is *not* one of these — it flows through `play_move` → `GameOver` → broadcast.
- `room.phase != "playing"` rejects moves before the second player joins and after the game ends — and is what makes the Postgres write fire exactly once (D7): once `phase == "over"`, every further frame is rejected here.

### `server/app/api/rooms.py` and `models/room.py`

```python
# models/room.py
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CreateRoomRequest(_CamelModel):
    display_name: str


class CreateRoomResponse(_CamelModel):
    code: str
    token: str
    player_index: int
```

```python
# api/rooms.py
import secrets

from fastapi import APIRouter, Request

from app.models.room import CreateRoomRequest, CreateRoomResponse
from app.store.room import Player, Room
from app.store.room_store import RoomStore

router = APIRouter(prefix="/rooms")


@router.post("")
async def create_room(body: CreateRoomRequest, request: Request) -> CreateRoomResponse:
    store: RoomStore = request.app.state.room_store
    code = await store.new_code()
    token = secrets.token_urlsafe(24)
    room = Room(code=code, players=[Player(index=0, display_name=body.display_name, token=token)])
    await store.create(room)
    return CreateRoomResponse(code=code, token=token, player_index=0)
```

The creator is player 0 with a token; they later connect via WS and `resume` with this token (D2).

### `server/app/main.py` (updated lifespan)

```python
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI

from app.api import router as api_router
from app.store.db import make_engine, make_session_factory
from app.store.room_store import RoomStore
from app.tmdb_client import HttpxTmdbClient
from app.ws import router as ws_router
from app.ws.manager import ConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    tmdb = HttpxTmdbClient(os.environ["TMDB_API_KEY"], httpx.AsyncClient())
    redis_client = redis.Redis.from_url(os.environ["REDIS_URL"])
    engine = make_engine(os.environ["DATABASE_URL"])

    app.state.tmdb_client = tmdb
    app.state.room_store = RoomStore(redis_client)
    app.state.connection_manager = ConnectionManager()
    app.state.session_factory = make_session_factory(engine)

    yield

    await tmdb.aclose()
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

Three resources opened at startup, closed at shutdown — same lifespan pattern as Phase 2, extended. `ConnectionManager` is process-local state, not a connection, so it's just instantiated.

### Alembic — `migrations/env.py` (async) + first migration

`alembic.ini` points `script_location = migrations` and leaves `sqlalchemy.url` empty (read from env). `migrations/env.py` runs migrations against the async engine:

```python
# migrations/env.py (key parts)
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.store.db_models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


asyncio.run(run_async_migrations())
```

```python
# migrations/versions/0001_create_games_table.py
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("room_code", sa.String(16), nullable=False),
        sa.Column("player_names", sa.JSON, nullable=False),
        sa.Column("winner_index", sa.Integer, nullable=False),
        sa.Column("chain", sa.JSON, nullable=False),
        sa.Column("losing_move", sa.JSON, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("games")
```

Run with `uv run alembic upgrade head` (needs `DATABASE_URL` set). In Phase 5 this becomes the Fly `release_command`.

---

## Testing strategy

Tests must use **no real infrastructure**. Three substitutions:

1. **Redis → `fakeredis.aioredis.FakeRedis`** — an in-memory async Redis that satisfies the same API. Injected by constructing `RoomStore(FakeRedis())` and assigning it onto `app.state` (or via a dependency override on a `get_room_store` accessor).
2. **Postgres → SQLite (`sqlite+aiosqlite://`)** — an in-memory async DB. Create tables with `Base.metadata.create_all` via `engine.begin()` in a fixture (no Alembic in tests). The `JSON` columns and the write path are DB-agnostic.
3. **TMDB → `FakeTmdbClient`** (from Phase 2's `tests/api/conftest.py`) — reused so `get_movie_credits` returns deterministic `cast_ids`.

### `server/tests/conftest.py` (update)

```python
import os

os.environ.setdefault("TMDB_API_KEY", "test-key-placeholder")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")     # unused; fakeredis overrides
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
```

### `server/tests/session/conftest.py` (sketch)

```python
import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.main import app
from app.store.db import make_session_factory
from app.store.db_models import Base
from app.store.room_store import RoomStore
from app.ws.manager import ConnectionManager
from tests.api.conftest import FakeTmdbClient   # reuse Phase 2 fake


@pytest.fixture()
async def wired_app():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.tmdb_client = FakeTmdbClient()
    app.state.room_store = RoomStore(fakeredis.aioredis.FakeRedis())
    app.state.connection_manager = ConnectionManager()
    app.state.session_factory = make_session_factory(engine)
    yield app
    await engine.dispose()


@pytest.fixture()
def client(wired_app) -> TestClient:
    # TestClient must NOT trigger the real lifespan (it would open real redis/db).
    # Construct without the context-manager form, or override lifespan to a no-op.
    return TestClient(wired_app)
```

`TestClient` supports WebSockets via `with client.websocket_connect("/ws/rooms/CODE") as ws: ws.send_json(...); ws.receive_json()`.

### Key test cases

| TC | Scenario | File |
| --- | --- | --- |
| R-01 | `POST /rooms` returns code + token + `playerIndex: 0` | `test_rooms.py` |
| R-02 | room code is 6 uppercase base32 chars | `test_rooms.py` |
| G-01 | creator `resume`s, second `join`s → both get `welcome`, phase flips `waiting`→`playing` | `test_gameplay.py` |
| G-02 | full valid game: moves alternate, `current_player_index` rotates, broadcasts reach both | `test_gameplay.py` |
| G-03 | invalid connection → `state` with `phase=over`, correct `winnerIndex`, `losingMove` set | `test_gameplay.py` |
| G-04 | move when not your turn → `error{code:"not_your_turn"}`, state unchanged | `test_gameplay.py` |
| G-05 | forfeit → `phase=over`, `losingMove=null`, previous player wins | `test_gameplay.py` |
| C-01 | reconnect with creator token → `welcome` with fresh snapshot, no new token | `test_reconnect.py` |
| C-02 | bad token on resume → `error{code:"bad_token"}`, socket closed | `test_reconnect.py` |
| C-03 | third `join` on a full room → `error{code:"room_full"}` | `test_reconnect.py` |
| H-01 | on `GameOver`, exactly one `games` row exists with correct winner/chain/names | `test_history.py` |
| H-02 | forfeit also writes a row with `losing_move = NULL` | `test_history.py` |

G-02/G-03 use `FakeTmdbClient`'s deterministic credits so a scripted move sequence has a known valid/invalid outcome — line up the fake's `cast_ids` with the actor IDs the test submits.

---

## Move-flow → engine mapping

| Wire event | Session step | Engine call |
| --- | --- | --- |
| `submit_move` (actor) | build `ActorMove` directly | `play_move(state, ActorMove)` |
| `submit_move` (movie) | `tmdb.get_movie_credits(id)` → `cast_ids` → `MovieMove` | `play_move(state, MovieMove)` |
| `forfeit` | none | `forfeit(state)` |
| result `InProgress` | `apply_in_progress` → `store.save` → broadcast | — |
| result `GameOver` | `apply_game_over` → `store.save` → `write_completed_game` → broadcast | — |

---

## Verification

Run from `server/`:

```bash
uv run ruff check .
uv run mypy app
uv run pytest                     # full suite: engine + api + session, all green
# migration sanity (needs a throwaway DATABASE_URL):
DATABASE_URL=sqlite+aiosqlite:///./tmp.db uv run alembic upgrade head
```

The Phase 1 and Phase 2 suites must stay green — they are the regression guard that the session layer didn't disturb the engine or proxy.

---

## Commit sequence

Each commit leaves the tree green (`mypy`/`ruff`/`pytest`):

1. `feat: add room domain model and redis-backed room store` — `store/room.py`, `store/room_store.py`, deps for redis, `pyproject.toml`
2. `feat: add postgres game history schema and write path` — `store/db.py`, `store/db_models.py`, `store/history.py`, `migrations/`, `alembic.ini`
3. `feat: add room creation REST endpoint` — `models/room.py`, `api/rooms.py`, router wiring
4. `feat: add websocket session layer with server-side validation` — `ws/messages.py`, `ws/manager.py`, `ws/room_socket.py`, lifespan wiring, session tests

Commits 1–2 add code with no caller (compiles, type-checks, but unexercised); 3–4 wire it into request paths and turn the session tests green.

---

## Risk flags

- **Single-instance only (D6).** The in-process `ConnectionManager` means a second backend instance can't broadcast to clients connected elsewhere. v1 runs one instance — fine for the master plan's scope. The scale path is Redis pub/sub for broadcast + a distributed lock; build it only if/when multi-instance is a goal.
- **TMDB fetch inside the room lock (D1).** A slow credits call holds the lock and stalls other frames for that room. Acceptable for 2-player turn-based play (one move in flight). If timers/spectators arrive, move the fetch outside the lock and re-validate the chain head after acquiring it.
- **`TestClient` must not run the real lifespan.** The lifespan opens real Redis/Postgres connections. Tests inject fakes onto `app.state` and must construct `TestClient` so it does **not** execute the startup lifespan (or override `lifespan` to a no-op in the fixture). If tests hang or `KeyError` on `REDIS_URL`, this is the cause.
- **`fakeredis` API parity.** `fakeredis.aioredis.FakeRedis` covers `get`/`set`/`exists`/`ex=` — everything `RoomStore` uses. If a future store method uses a command fakeredis doesn't implement, swap to a real Redis container in CI (`services:` in the workflow).
- **Alembic async env.** The default `alembic init` template is **sync**. Use the async `env.py` shown above (`run_sync(do_run_migrations)`), or `alembic init -t async`. A sync template against `postgresql+asyncpg://` fails at connect.
- **Exactly-once Postgres write (D7).** Guaranteed only because `_handle_frame` rejects all frames once `phase == "over"`. If a code path ever mutates a terminal room, dedup (unique on `room_code` won't work — codes are reused after expiry; use an idempotency check on `ended_at` already set, or a per-game UUID).
- **Token in `WelcomeMessage` only.** The fresh-join token is sent once, to the joining socket only, and never appears in `StateView` (D5). A regression that leaks `Room.players[].token` into a broadcast would hand every client every player's identity — the `StateView`/`PlayerView` split is the guard; keep `Player` out of any broadcast model.
- **`REDIS_URL`/`DATABASE_URL` at startup.** Like `TMDB_API_KEY` in Phase 2, these are read in the lifespan and fail fast if absent. Phase 5 supplies them via Fly secrets; local dev needs them in the shell or a `.env` loaded before `uvicorn`.
```
