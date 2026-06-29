# Phase 4 Implementation Plan — React Client

Source of scope: [PYTHON_TS_REWRITE_PLAN.md](PYTHON_TS_REWRITE_PLAN.md#phase-4-react-client)
Wire contracts (authoritative): [PHASE_2_PLAN.md](PHASE_2_PLAN.md) (REST), [PHASE_3_PLAN.md](PHASE_3_PLAN.md) (WS protocol, `POST /rooms`)
Server status assumed: Phases 0–3 complete — engine, TMDB proxy, room/session layer, Postgres history write all live.

**Done when:** two browser tabs (locally, against the dev server) can create/join a room, play a full game with live updates on both sides, reach a game-over screen, and view the finished game in a history list/detail. The web build, lint, typecheck, and tests are green in CI. (The *public-internet, two-device* bar is Phase 5 — Phase 4's "done when" is local-stack end-to-end.)

**Audience:** Senior engineer fluent in TypeScript and React. The novel parts here are the **boundary** (all game/session logic in `packages/game-client`, `web/` as UI-only) and the **reconnect-capable WebSocket client**, not React basics — those get the depth.

---

## What we're building

Three things, in dependency order:

1. **Server: history read endpoints** — `GET /games` (list) and `GET /games/{id}` (detail), reading the Postgres `games` table Phase 3 writes. Deferred from Phase 3 (PHASE_3_PLAN D8) to land with their only consumer.
2. **`packages/game-client`** — the framework-light core: TypeScript types mirroring the server DTOs, a `RestClient`, a reconnect-capable `GameSocket`, and React hooks (`useGameRoom`, `useMoveSearch`). This is where REST calls, the WS client, state types, and reconnect handling live (master plan requirement). React is a *peer* dependency — the package is reusable by a future React Native app with no change (the explicit reason the boundary exists; see PYTHON_TS_REWRITE_PLAN "packages/game-client exists from day one").
3. **`web/`** — the Vite + React + TS + Tailwind app, scaffolded here (deferred from Phase 0). UI only: screens and components that consume `game-client` hooks. It contains no `fetch`, no `WebSocket`, no game rules.

### The boundary, concretely

```
web/  (UI only)
  screens + components  ──consumes──▶  @bacons-law/game-client
                                          ├── types.ts      (DTOs)
                                          ├── rest.ts       (RestClient)
                                          ├── socket.ts     (GameSocket: connect/reconnect)
                                          └── hooks/         (useGameRoom, useMoveSearch)
```

If a component imports `fetch`, `WebSocket`, or constructs a `Move`, it's in the wrong layer. The lint rule in D7 enforces this mechanically.

---

## Design decisions

### D1 — React hooks live in `game-client`, not `web/`

The master plan says "web/ consumes it via hooks" and "all game/session logic lives in `packages/game-client`." A future React Native app is **also** React — so React hooks that wrap the socket/REST core are reusable by RN unchanged. What is *not* reusable (and must stay out of the package) is anything touching the DOM, `react-router`, `localStorage` directly, or Tailwind. The package depends on `react` as a **peer** dependency; persistence is injected (D4).

**Trade-off:** `web/` can't define its own bespoke hooks trivially — it goes through the package. Benefit: the RN app gets the entire stateful client for free, which is the whole point of the boundary.

### D2 — `GameSocket` is a framework-agnostic class with a callback/event API; the hook adapts it to React

The socket client is a plain TS class: `connect()`, `submitMove()`, `forfeit()`, `close()`, and an `onState`/`onError`/`onStatusChange` listener API. It knows nothing about React. `useGameRoom` is a thin adapter that subscribes the class's events to `useState`/`useEffect`. This keeps the hard part (reconnect, message framing) testable without a renderer and reusable outside React if ever needed.

### D3 — Reconnect: token-first, auto-resume with backoff

The client persists `{ code, token, playerIndex }` per room. On (re)connect:
- If a token exists for this room → send `resume{token}`.
- Else (fresh second player) → send `join{displayName}`, store the `token` from `welcome`.

On unexpected socket close while the game is live, `GameSocket` auto-reconnects with capped exponential backoff and re-sends `resume`. This is exactly the v1 reconnect scope: "a client with a valid token can rejoin and receive a fresh snapshot" — no turn timers, no AFK handling (master plan, "Reconnect scope (v1)").

### D4 — Persistence is injected, not hard-coded to `localStorage`

`GameSocket`/`useGameRoom` take a small `TokenStore` interface (`get(code)`, `set(code, creds)`, `clear(code)`). `web/` supplies a `localStorage`-backed implementation; RN would supply `AsyncStorage`. The package never imports `localStorage` directly — that keeps it DOM-free (D1).

### D5 — Move type the UI must search is **derived from server state**, not tracked client-side

The next move must be an Actor after a Movie (and vice-versa); the first move is an Actor (UI rule, GAME_SPEC_V2 boundary table). The client derives this from the broadcast `StateView`: empty chain or last move is a movie → search actors; else search movies. The client never *decides* validity — it only picks which search endpoint to hit and which input affordance to show. The server remains authoritative (PHASE_3_PLAN D1). This mirrors the Kotlin `nextMoveType()` derivation (GAME_REPOSITORY_REFACTOR, Step 4).

### D6 — Debounced search through REST; selection sends a thin move over WS

Typing hits `GET /movies/search` / `GET /people/search` (debounced ~300ms, latest-wins). Selecting a result sends `submit_move` with only `{kind, id, displayText, releaseYear?}` — **no `cast_ids`** (the server re-fetches; PHASE_3_PLAN D1). Search is stateless REST; moves are stateful WS. Same split as the Kotlin two-phase flow (search candidates → enrich on select), except enrichment now happens server-side.

### D7 — Mobile-first responsive layout; enforce the boundary with a lint rule

Mobile portrait is the **primary** target (master plan: "mobile-responsive layout as the primary target, not a stretch case"). Tailwind utility classes, single-column by default, widen at `sm:`/`md:`. An ESLint `no-restricted-imports`/`no-restricted-globals` rule forbids `fetch`, `WebSocket`, and `localStorage` inside `web/src/` so the boundary can't erode silently.

### D8 — State shape the UI renders is a single `RoomView`

`useGameRoom` exposes one object the screens switch on — phase (`connecting | waiting | playing | over | error`), players, chain, whose turn, my index, and the actions (`submitMove`, `forfeit`). Screens are a `switch (room.phase)`. This is the React analogue of the Kotlin `GameScreenUiState` sealed interface (GAME_REPOSITORY_REFACTOR, Step 4) — one state surface, exhaustive rendering.

---

## Part 1 — Server: history read endpoints

Small, isolated addition. Read-only, no new infra.

### `server/app/models/history.py` (new)

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class GameSummary(_CamelModel):
    id: int
    room_code: str
    player_names: list[str]
    winner_index: int
    move_count: int
    ended_at: datetime


class GameDetail(_CamelModel):
    id: int
    room_code: str
    player_names: list[str]
    winner_index: int
    chain: list[dict]            # serialized MoveModels (camelCase already)
    losing_move: dict | None
    started_at: datetime
    ended_at: datetime
```

### `server/app/api/history.py` (new)

```python
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.history import GameDetail, GameSummary
from app.store.db_models import GameRecord

router = APIRouter(prefix="/games")


@router.get("")
async def list_games(request: Request, limit: int = 50) -> list[GameSummary]:
    factory: async_sessionmaker = request.app.state.session_factory
    async with factory() as session:
        rows = (
            await session.execute(
                select(GameRecord).order_by(GameRecord.ended_at.desc()).limit(limit)
            )
        ).scalars().all()
    return [
        GameSummary(
            id=r.id,
            room_code=r.room_code,
            player_names=r.player_names,
            winner_index=r.winner_index,
            move_count=len(r.chain),
            ended_at=r.ended_at,
        )
        for r in rows
    ]


@router.get("/{game_id}")
async def get_game(game_id: int, request: Request) -> GameDetail:
    factory: async_sessionmaker = request.app.state.session_factory
    async with factory() as session:
        record = await session.get(GameRecord, game_id)
    if record is None:
        raise HTTPException(status_code=404, detail="game not found")
    return GameDetail(
        id=record.id,
        room_code=record.room_code,
        player_names=record.player_names,
        winner_index=record.winner_index,
        chain=record.chain,
        losing_move=record.losing_move,
        started_at=record.started_at,
        ended_at=record.ended_at,
    )
```

Wire `history.router` into `app/api/__init__.py`. Tests (`tests/session/test_history.py` extension): insert two `GameRecord`s via the test session, assert `GET /games` returns them newest-first and `GET /games/{id}` returns the chain; unknown id → 404.

### CORS (needed once the browser app calls the API cross-origin in dev)

Add `CORSMiddleware` in `main.py`, allowed origins from an env var (`WEB_ORIGIN`, default `http://localhost:5173` for Vite dev):

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("WEB_ORIGIN", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
```

WebSockets are not subject to CORS, but the REST search/history/`POST /rooms` calls are.

---

## Part 2 — `packages/game-client`

Promotes the Phase 0 placeholder package to a real implementation.

### `packages/game-client/package.json` (update)

```json
{
  "name": "@bacons-law/game-client",
  "version": "0.1.0",
  "type": "module",
  "main": "./src/index.ts",
  "scripts": {
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "peerDependencies": { "react": ">=18" },
  "devDependencies": {
    "react": "^18.3.1",
    "@types/react": "^18.3.12",
    "typescript": "^5.6.3",
    "vitest": "^2.1.8"
  }
}
```

React is a **peer** dependency (D1) — the consuming app provides the single React instance; the package doesn't bundle its own.

### `src/types.ts` — mirror the server DTOs

These mirror `app/ws/messages.py` and `app/models/*` exactly (camelCase, the wire contract). Keep them hand-written and reviewed against the server — they are the client's copy of the one-way-door contract.

```ts
export type MoveKind = "actor" | "movie";

export interface ActorMove { kind: "actor"; id: number; displayText: string; imagePath?: string | null; }
export interface MovieMove {
  kind: "movie"; id: number; displayText: string;
  castIds?: number[];           // present on server->client; omitted on submit (server re-fetches)
  imagePath?: string | null; releaseYear?: string | null;
}
export type Move = ActorMove | MovieMove;

export interface PlayerView { index: number; displayName: string; connected: boolean; }

export type Phase = "waiting" | "playing" | "over";

export interface StateView {
  type: "state";
  code: string;
  phase: Phase;
  players: PlayerView[];
  moves: Move[];
  currentPlayerIndex: number;
  winnerIndex?: number | null;
  losingMove?: Move | null;
}

export interface WelcomeMessage { type: "welcome"; playerIndex: number; token?: string | null; state: StateView; }
export interface ErrorMessage { type: "error"; message: string; code: string; }
export type ServerMessage = WelcomeMessage | StateView | ErrorMessage;

// client -> server
export type ClientMessage =
  | { type: "join"; displayName: string }
  | { type: "resume"; token: string }
  | { type: "submit_move"; move: Move }
  | { type: "forfeit" };

// REST DTOs
export interface CreateRoomResponse { code: string; token: string; playerIndex: number; }
export interface MovieSearchResult { id: number; title: string; releaseYear?: string | null; posterPath?: string | null; }
export interface PersonSearchResult { id: number; name: string; profilePath?: string | null; }
export interface GameSummary { id: number; roomCode: string; playerNames: string[]; winnerIndex: number; moveCount: number; endedAt: string; }
export interface GameDetail { id: number; roomCode: string; playerNames: string[]; winnerIndex: number; chain: Move[]; losingMove?: Move | null; startedAt: string; endedAt: string; }
```

### `src/config.ts`

```ts
export interface ClientConfig {
  /** e.g. http://localhost:8000 */
  apiBaseUrl: string;
  /** e.g. ws://localhost:8000 ; derived from apiBaseUrl if omitted */
  wsBaseUrl?: string;
}

export function wsBase(cfg: ClientConfig): string {
  if (cfg.wsBaseUrl) return cfg.wsBaseUrl;
  return cfg.apiBaseUrl.replace(/^http/, "ws");   // http->ws, https->wss
}
```

### `src/rest.ts`

```ts
import type { ClientConfig } from "./config";
import type {
  CreateRoomResponse, GameDetail, GameSummary, MovieSearchResult, PersonSearchResult,
} from "./types";

export class RestClient {
  constructor(private readonly cfg: ClientConfig) {}

  private async getJson<T>(path: string): Promise<T> {
    const res = await fetch(`${this.cfg.apiBaseUrl}${path}`);
    if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
    return res.json() as Promise<T>;
  }

  createRoom(displayName: string): Promise<CreateRoomResponse> {
    return fetch(`${this.cfg.apiBaseUrl}/rooms`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ displayName }),
    }).then((r) => {
      if (!r.ok) throw new Error(`POST /rooms -> ${r.status}`);
      return r.json() as Promise<CreateRoomResponse>;
    });
  }

  searchMovies(q: string): Promise<MovieSearchResult[]> {
    return this.getJson(`/movies/search?query=${encodeURIComponent(q)}`);
  }
  searchPeople(q: string): Promise<PersonSearchResult[]> {
    return this.getJson(`/people/search?query=${encodeURIComponent(q)}`);
  }
  listGames(): Promise<GameSummary[]> { return this.getJson(`/games`); }
  getGame(id: number): Promise<GameDetail> { return this.getJson(`/games/${id}`); }
}
```

### `src/socket.ts` — reconnect-capable WS client (D2/D3)

```ts
import type { ClientConfig } from "./config";
import { wsBase } from "./config";
import type { ClientMessage, ErrorMessage, Move, ServerMessage, StateView } from "./types";

export interface RoomCreds { code: string; token: string; playerIndex: number; }
export interface TokenStore {
  get(code: string): RoomCreds | null;
  set(code: string, creds: RoomCreds): void;
  clear(code: string): void;
}

export type SocketStatus = "connecting" | "open" | "reconnecting" | "closed";

interface GameSocketOpts {
  cfg: ClientConfig;
  code: string;
  /** display name used when joining as a fresh player (no token yet) */
  displayName: string;
  tokens: TokenStore;
  onState: (s: StateView) => void;
  onError: (e: ErrorMessage) => void;
  onStatus: (s: SocketStatus) => void;
}

export class GameSocket {
  private ws: WebSocket | null = null;
  private closedByUs = false;
  private backoffMs = 500;
  private readonly maxBackoff = 8000;

  constructor(private readonly o: GameSocketOpts) {}

  connect(): void {
    this.closedByUs = false;
    this.o.onStatus(this.ws ? "reconnecting" : "connecting");
    const ws = new WebSocket(`${wsBase(this.o.cfg)}/ws/rooms/${this.o.code}`);
    this.ws = ws;

    ws.onopen = () => {
      this.backoffMs = 500;
      this.o.onStatus("open");
      const creds = this.o.tokens.get(this.o.code);
      this.send(creds ? { type: "resume", token: creds.token }
                      : { type: "join", displayName: this.o.displayName });
    };

    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data) as ServerMessage;
      if (msg.type === "welcome") {
        if (msg.token) {
          this.o.tokens.set(this.o.code, {
            code: this.o.code, token: msg.token, playerIndex: msg.playerIndex,
          });
        }
        this.o.onState(msg.state);
      } else if (msg.type === "state") {
        this.o.onState(msg);
      } else {
        this.o.onError(msg);
      }
    };

    ws.onclose = () => {
      if (this.closedByUs) { this.o.onStatus("closed"); return; }
      this.o.onStatus("reconnecting");
      setTimeout(() => this.connect(), this.backoffMs);
      this.backoffMs = Math.min(this.backoffMs * 2, this.maxBackoff);
    };
  }

  submitMove(move: Move): void {
    // strip castIds before sending — server is authoritative (PHASE_3 D1)
    const lean: Move = move.kind === "movie"
      ? { kind: "movie", id: move.id, displayText: move.displayText, releaseYear: move.releaseYear }
      : move;
    this.send({ type: "submit_move", move: lean });
  }
  forfeit(): void { this.send({ type: "forfeit" }); }

  close(): void { this.closedByUs = true; this.ws?.close(); }

  private send(msg: ClientMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }
}
```

Notes:
- Reconnect re-runs `connect()`; `onopen` always re-sends `resume` (the token now exists), so a dropped socket transparently re-establishes and the next `welcome.state` is the fresh snapshot (D3).
- `closedByUs` distinguishes an intentional `close()` (no retry) from a network drop (retry with backoff).
- `submitMove` strips `castIds` (D6) — belt-and-suspenders even though the server ignores them.

### `src/hooks/useGameRoom.ts` — React adapter (D2/D8)

```ts
import { useEffect, useMemo, useRef, useState } from "react";
import type { ClientConfig } from "../config";
import { GameSocket } from "../socket";
import type { TokenStore } from "../socket";
import type { ErrorMessage, Move, StateView } from "../types";

export type RoomPhase = "connecting" | "waiting" | "playing" | "over" | "error";

export interface RoomView {
  phase: RoomPhase;
  state: StateView | null;
  myIndex: number | null;
  isMyTurn: boolean;
  error: string | null;
  submitMove: (m: Move) => void;
  forfeit: () => void;
}

export function useGameRoom(
  cfg: ClientConfig, code: string, displayName: string, tokens: TokenStore,
): RoomView {
  const [state, setState] = useState<StateView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(true);
  const sockRef = useRef<GameSocket | null>(null);

  useEffect(() => {
    const sock = new GameSocket({
      cfg, code, displayName, tokens,
      onState: (s) => { setState(s); setConnecting(false); setError(null); },
      onError: (e: ErrorMessage) => setError(e.message),
      onStatus: (st) => setConnecting(st === "connecting"),
    });
    sockRef.current = sock;
    sock.connect();
    return () => sock.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  const myIndex = tokens.get(code)?.playerIndex ?? null;

  return useMemo<RoomView>(() => {
    const phase: RoomPhase =
      error ? "error" : connecting && !state ? "connecting" : state ? state.phase : "connecting";
    return {
      phase,
      state,
      myIndex,
      isMyTurn: !!state && state.phase === "playing" && state.currentPlayerIndex === myIndex,
      error,
      submitMove: (m) => sockRef.current?.submitMove(m),
      forfeit: () => sockRef.current?.forfeit(),
    };
  }, [state, error, connecting, myIndex]);
}
```

### `src/hooks/useMoveSearch.ts` — debounced, type-derived search (D5/D6)

```ts
import { useEffect, useState } from "react";
import { RestClient } from "../rest";
import type { ClientConfig } from "../config";
import type { Move, StateView } from "../types";

export type SearchKind = "actor" | "movie";

export function nextMoveKind(state: StateView | null): SearchKind {
  if (!state || state.moves.length === 0) return "actor";
  return state.moves[state.moves.length - 1].kind === "movie" ? "actor" : "movie";
}

export interface Candidate { move: Move; subtitle?: string; imageUrl?: string | null; }

export function useMoveSearch(cfg: ClientConfig, kind: SearchKind, query: string): {
  results: Candidate[]; loading: boolean;
} {
  const [results, setResults] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    let cancelled = false;
    const rest = new RestClient(cfg);
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        if (kind === "actor") {
          const people = await rest.searchPeople(query);
          if (!cancelled) setResults(people.map((p) => ({
            move: { kind: "actor", id: p.id, displayText: p.name, imagePath: p.profilePath },
            imageUrl: p.profilePath,
          })));
        } else {
          const movies = await rest.searchMovies(query);
          if (!cancelled) setResults(movies.map((m) => ({
            move: { kind: "movie", id: m.id, displayText: m.title, releaseYear: m.releaseYear },
            subtitle: m.releaseYear ?? undefined,
          })));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 300);   // debounce
    return () => { cancelled = true; clearTimeout(t); };
  }, [cfg, kind, query]);

  return { results, loading };
}
```

`nextMoveKind` is the derived-search-type rule (D5). Movie candidates carry no image (poster art spoils cast — same rationale as the Kotlin `MoveCandidate`, GAME_REPOSITORY_REFACTOR Step 2).

### `src/index.ts` (barrel)

```ts
export * from "./types";
export * from "./config";
export { RestClient } from "./rest";
export { GameSocket } from "./socket";
export type { RoomCreds, TokenStore, SocketStatus } from "./socket";
export { useGameRoom, nextMoveKind } from "./hooks/useGameRoom";
export { useMoveSearch } from "./hooks/useMoveSearch";
export type { RoomView, RoomPhase } from "./hooks/useGameRoom";
export type { Candidate, SearchKind } from "./hooks/useMoveSearch";
```

### Package tests (vitest)

The framework-agnostic core is unit-testable without a browser. Use `vitest` with a mock `WebSocket`:

| TC | Scenario |
| --- | --- |
| S-01 | fresh connect with no token → sends `join`; stores token from `welcome` |
| S-02 | connect with existing token → sends `resume`, no token stored |
| S-03 | `submitMove(movie)` strips `castIds` from the sent frame |
| S-04 | socket close (not by us) → reconnect attempted with backoff; close() → no retry |
| U-01 | `nextMoveKind`: empty→actor, last movie→actor, last actor→movie |

---

## Part 3 — `web/`

### Scaffold

```
web/
├── index.html
├── package.json              # react, react-dom, react-router-dom, @bacons-law/game-client (workspace:*)
├── vite.config.ts            # react plugin; dev proxy /api -> :8000 (optional)
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
├── .eslintrc.cjs             # no-restricted fetch/WebSocket/localStorage in src (D7)
└── src/
    ├── main.tsx              # ReactDOM root + Router
    ├── App.tsx               # routes
    ├── config.ts             # reads VITE_API_BASE_URL -> ClientConfig
    ├── tokenStore.ts         # localStorage-backed TokenStore (D4)
    ├── screens/
    │   ├── HomeScreen.tsx          # create or join
    │   ├── GameScreen.tsx          # the room: switch on RoomView.phase
    │   ├── GameOverScreen.tsx      # winner + final chain + play again
    │   ├── HistoryListScreen.tsx   # GET /games
    │   └── HistoryDetailScreen.tsx # GET /games/{id}
    └── components/
        ├── ChainView.tsx           # rendered move chain
        ├── SearchPanel.tsx         # input + results list (useMoveSearch)
        ├── TurnBanner.tsx          # "Your turn" / "Waiting for X"
        └── ConnectionBadge.tsx     # reconnecting indicator
```

`pnpm-workspace.yaml` adds `web` (Phase 0 deliberately omitted it):

```yaml
packages:
  - "packages/*"
  - "web"
```

### `web/src/config.ts` and `tokenStore.ts`

```ts
// config.ts
import type { ClientConfig } from "@bacons-law/game-client";
export const config: ClientConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
};
```

```ts
// tokenStore.ts — the only place localStorage is touched (D4/D7)
import type { RoomCreds, TokenStore } from "@bacons-law/game-client";

export const localTokenStore: TokenStore = {
  get: (code) => {
    const raw = localStorage.getItem(`room:${code}`);
    return raw ? (JSON.parse(raw) as RoomCreds) : null;
  },
  set: (code, creds) => localStorage.setItem(`room:${code}`, JSON.stringify(creds)),
  clear: (code) => localStorage.removeItem(`room:${code}`),
};
```

The ESLint rule (D7) exempts `tokenStore.ts` — it's the deliberate persistence seam.

### `web/src/screens/GameScreen.tsx` (shape)

```tsx
import { useState } from "react";
import { useParams } from "react-router-dom";
import { useGameRoom, useMoveSearch, nextMoveKind } from "@bacons-law/game-client";
import { config } from "../config";
import { localTokenStore } from "../tokenStore";

export function GameScreen({ displayName }: { displayName: string }) {
  const { code = "" } = useParams();
  const room = useGameRoom(config, code, displayName, localTokenStore);
  const [query, setQuery] = useState("");
  const kind = nextMoveKind(room.state);
  const { results, loading } = useMoveSearch(config, kind, room.isMyTurn ? query : "");

  switch (room.phase) {
    case "connecting": return <Centered>Connecting…</Centered>;
    case "error":      return <Centered>Something went wrong: {room.error}</Centered>;
    case "waiting":    return <WaitingRoom code={code} state={room.state!} />;
    case "over":       return <GameOverPanel state={room.state!} myIndex={room.myIndex} />;
    case "playing":
      return (
        <div className="flex flex-col gap-4 p-4 max-w-md mx-auto">
          <TurnBanner state={room.state!} myIndex={room.myIndex} />
          <ChainView moves={room.state!.moves} />
          {room.isMyTurn ? (
            <SearchPanel
              kind={kind} query={query} onQuery={setQuery}
              results={results} loading={loading}
              onSelect={(c) => { room.submitMove(c.move); setQuery(""); }}
            />
          ) : (
            <p className="text-center opacity-70">Waiting for the other player…</p>
          )}
          <button className="text-sm underline opacity-60" onClick={room.forfeit}>
            Give up
          </button>
        </div>
      );
  }
}
```

One `switch (room.phase)`, exhaustive — the React form of the Kotlin `when (screenUiState)` (D8). The search input only renders/searches on your turn; selecting a candidate calls `room.submitMove`.

### Routing (`App.tsx`)

```
/                      HomeScreen      (create room | join by code)
/rooms/:code           GameScreen      (gameplay; resumes via stored token)
/history               HistoryListScreen
/history/:id           HistoryDetailScreen
```

Create flow: `HomeScreen` calls `RestClient.createRoom(name)`, stores creds in `localTokenStore`, navigates to `/rooms/:code`. Join flow: enters a code + name, navigates to `/rooms/:code` (the socket sends `join` since no token exists yet). Reload mid-game: `/rooms/:code` finds a stored token and `resume`s automatically (D3).

### CI — add `web-ci` job

Extend `.github/workflows/ci.yml` (deferred from Phase 0):

```yaml
  web-ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20", cache: "pnpm" }
      - run: pnpm install --frozen-lockfile
      - run: pnpm -r typecheck
      - run: pnpm -r test
      - run: pnpm --filter web build
```

`pnpm -r` runs across the workspace (game-client + web). `pnpm-lock.yaml` must be regenerated and committed after adding `web` and the package deps.

---

## End-to-end verification (local, the Phase 4 "done when")

Three processes: backend (with Redis + Postgres reachable), and the Vite dev server.

```bash
# terminal 1 — infra (docker, or local installs)
#   redis on :6379, postgres on :5432; run alembic upgrade head once
# terminal 2 — backend
cd server && uv run alembic upgrade head
REDIS_URL=redis://localhost:6379/0 \
DATABASE_URL=postgresql+asyncpg://localhost/baconslaw \
TMDB_API_KEY=... uv run uvicorn app.main:app --reload
# terminal 3 — web
cd web && VITE_API_BASE_URL=http://localhost:8000 pnpm dev
```

Manual check: open `http://localhost:5173` in **two tabs**. Tab A creates a room, reads the code; Tab B joins with the code. Play actor→movie→actor… in alternation; both tabs update live on every move. Force an invalid connection → both land on game-over with the correct winner. Reload Tab B mid-game → it resumes to the current chain. Visit `/history` → the finished game is listed; open it → the chain renders.

Automated gates:

```bash
cd server && uv run ruff check . && uv run mypy app && uv run pytest   # incl. new history endpoint tests
pnpm -r typecheck && pnpm -r test && pnpm --filter web build
```

---

## DTO ↔ screen mapping

| Server contract | game-client type | Consumed by |
| --- | --- | --- |
| `POST /rooms` → `CreateRoomResponse` | `RestClient.createRoom` | HomeScreen |
| `welcome` / `state` (WS) | `useGameRoom` → `RoomView` | GameScreen |
| `GET /movies\|people/search` | `useMoveSearch` → `Candidate[]` | SearchPanel |
| `submit_move` / `forfeit` (WS) | `RoomView.submitMove` / `.forfeit` | GameScreen |
| `GET /games` → `GameSummary[]` | `RestClient.listGames` | HistoryListScreen |
| `GET /games/{id}` → `GameDetail` | `RestClient.getGame` | HistoryDetailScreen |

---

## Commit sequence

1. `feat: add game history read endpoints` — `models/history.py`, `api/history.py`, router + CORS wiring, tests (server-only; ships independently)
2. `feat: implement game-client types, rest, and socket core` — `packages/game-client/src/{types,config,rest,socket}.ts` + vitest
3. `feat: add game-client react hooks` — `hooks/useGameRoom.ts`, `hooks/useMoveSearch.ts`, barrel
4. `feat: scaffold web app shell and routing` — Vite/Tailwind/router setup, `config.ts`, `tokenStore.ts`, `App.tsx`, workspace + CI
5. `feat: build game, game-over, and history screens` — screens + components
6. `chore: regenerate pnpm lockfile and wire web-ci`

Commit 1 is a self-contained server change. 2–3 build the package bottom-up (each `pnpm --filter @bacons-law/game-client typecheck`-clean). 4–6 assemble the UI.

---

## Risk flags

- **DTO drift between `types.ts` and the server.** The TS types are a hand-maintained copy of the Python wire contract — they can silently diverge. The camelCase tests on the server (Phase 2) and the WS protocol tests (Phase 3) pin the server side; keep `types.ts` reviewed against `ws/messages.py` and `models/*`. A generated OpenAPI→TS step is a candidate improvement but out of scope here.
- **Reconnect storms.** If the server is down, `GameSocket` retries forever with capped backoff. Fine for v1, but a permanently-dead server means an infinite (slow) retry loop. Add a max-attempts cap if it becomes a problem; not needed for the local/Phase-5 target.
- **`isMyTurn` derives from a possibly-stale `tokens.get(code)?.playerIndex`.** `myIndex` comes from persisted creds, set on `welcome`. Until the first `welcome` arrives, `myIndex` may be null (creator) — guarded by `phase === "connecting"`. Verify the creator path (token already stored from `POST /rooms`) sets `playerIndex: 0` in creds before navigating.
- **CORS in dev.** The browser blocks REST calls to `:8000` from `:5173` unless `CORSMiddleware` allows the Vite origin. Either set `WEB_ORIGIN` or use a Vite dev proxy. WS is unaffected. Easy to miss until the first `fetch` fails with a CORS error.
- **Boundary erosion.** Without the D7 lint rule, a hurried component will inline a `fetch` or `new WebSocket`. The rule is the enforcement; treat a `// eslint-disable` on it in `web/src/` as a review red flag (except the sanctioned `tokenStore.ts`).
- **`localStorage` token leakage between rooms.** Keyed by `room:{code}`; clearing happens on "play again". A stale token for a long-expired room (Redis TTL passed) will fail `resume` with `bad_token` — handle that by clearing creds and falling back to `join`/home on a `bad_token` error.
- **Single React instance.** `react` as a peer dep relies on the workspace hoisting one copy. If `web/` and the package resolve different React versions, hooks break with the "invalid hook call" error. `pnpm` dedupes within the workspace; verify after `pnpm install`.
```
