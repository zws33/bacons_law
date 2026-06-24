# Phase 5 Implementation Plan — Deploy + Playtest

Source of scope: [PYTHON_TS_REWRITE_PLAN.md](PYTHON_TS_REWRITE_PLAN.md#phase-5-deploy--playtest)
Builds on: Phases 0–4 complete — full local stack (FastAPI + Redis + Postgres + React) plays a game end-to-end.

**Done when:** the Phase 4 "done when" criterion is met against the **deployed** (not local) stack — two people, two separate devices, on the public internet, complete a full game start to finish through the deployed web app, and the finished game appears in the deployed history view. This is the acceptance test for the entire initiative.

**Audience:** Senior engineer comfortable with containers and cloud deploys, newer to Fly.io specifically. Fly-specific mechanics (Machines, `fly.toml`, secrets, release commands, colocated Redis/Postgres) are explained where they differ from Cloud Run / Kubernetes / Heroku mental models.

---

## What we're doing

No new product features. Phase 5 is operational: package the server into a container, stand up Redis and Postgres next to it on Fly.io, run migrations on deploy, deploy the web build to a static host, point it at the deployed API, and run the two-device playtest.

The hosting decision was made up front (PYTHON_TS_REWRITE_PLAN, "Hosting is Fly.io, not Cloud Run"): **persistent WebSocket connections and in-process session state** (Phase 3's `ConnectionManager`, D6) are fundamentally incompatible with scale-to-zero / multi-instance autoscaling. Fly.io runs long-lived processes and offers colocated Redis and Postgres, keeping all stateful infra in one place.

Five deliverables:

1. **`Dockerfile`** — a uv-based image for the FastAPI server.
2. **`fly.toml`** — Fly app config: one Machine, internal port, WebSocket-friendly, Alembic as the release command.
3. **Managed Redis + Postgres** on Fly, wired via secrets.
4. **Web static deploy** (Vercel or Netlify — decided *now*, not before) pointed at the Fly API.
5. **Two-device playtest** — the acceptance run, with a short checklist.

---

## Concepts: Fly.io for a Cloud Run / K8s mind

| Concept | Cloud Run / K8s | Fly.io |
| --- | --- | --- |
| Unit of compute | Container revision / Pod | **Machine** (a fast-booting Firecracker VM) |
| Config | `service.yaml` / Helm | `fly.toml` |
| Secrets | Secret Manager / `Secret` | `fly secrets set` (injected as env) |
| Scale to zero | default | **off** for this app (`min_machines_running = 1`) |
| Migrations on deploy | init container / job | `[deploy] release_command` |
| Managed Postgres | Cloud SQL | **Fly Postgres** (or Fly Managed Postgres) |
| Managed Redis | Memorystore | **Upstash Redis on Fly** (`fly redis create`) |
| Internal networking | VPC | `.internal` / `.flycast` private DNS |

The key Fly difference for *this* app: we **pin one always-on Machine** (`min_machines_running = 1`, no autoscaling). The in-process `ConnectionManager` and per-room `asyncio.Lock` (Phase 3, D6) assume a single instance. Multiple Machines would split connections across processes that can't broadcast to each other — the multi-instance scaling that the master plan explicitly defers. **One Machine is a correctness requirement in v1, not a cost choice.**

---

## Design decisions

### D1 — One pinned Machine, autoscaling off (correctness, not thrift)

`min_machines_running = 1`, `auto_stop_machines = false`. Single-instance is required by the in-process connection registry (Phase 3 D6). This is documented in `fly.toml` with a comment so a future "let's scale this up" doesn't silently break broadcasts. Lifting it is the same work as the deferred multi-instance scaling (Redis pub/sub fan-out + distributed lock).

### D2 — Alembic runs as the Fly `release_command`, not in the app boot path

Migrations run once per deploy, before the new Machine serves traffic, via `[deploy] release_command = "alembic upgrade head"`. Running migrations inside the FastAPI lifespan would re-run them on every boot/restart and couple app startup to DB DDL — wrong layer. The release command runs in a temporary Machine with the same image and secrets; if it fails, the deploy aborts and the old version keeps serving.

### D3 — Managed Redis and Postgres, colocated on Fly

`fly redis create` (Upstash) and `fly postgres create` (or Managed Postgres). Both injected as secrets (`REDIS_URL`, `DATABASE_URL`). Colocating them on Fly keeps latency low and infra in one dashboard — the stated reason Fly was chosen over Cloud Run, which would have needed external/managed state services wired across providers.

### D4 — Web on a static host (Vercel), decided at this phase

The master plan deliberately deferred the static-host choice to Phase 5 ("decide at this phase, not before; no architectural dependency on the choice"). **Decision: Vercel.** Rationale: zero-config Vite builds, instant preview deploys per PR, free tier sufficient, and a single env var (`VITE_API_BASE_URL`) is the only coupling. Netlify is equivalent; the choice is reversible (it's a static bundle) — a two-way door, so it gets a fast decision. The web app is a pure static SPA; the host only serves files and does SPA-fallback routing.

### D5 — `wss://` and CORS are the two cross-origin seams to get right

The browser app (Vercel origin) talks to the Fly API over two protocols: REST (`https://`, subject to CORS) and WebSocket (`wss://`, not subject to CORS but must terminate TLS at Fly's edge). Two config points:
- Server `WEB_ORIGIN` secret = the Vercel production URL (and preview URLs if desired) → `CORSMiddleware` allow-list (Phase 4, Part 1).
- Web `VITE_API_BASE_URL` = `https://<app>.fly.dev`; the client derives `wss://<app>.fly.dev` from it (`config.ts wsBase`, Phase 4).

Fly terminates TLS and proxies WebSocket upgrades transparently, so no app-side TLS or upgrade handling is needed — but the health check and the `[http_service]` must not buffer/timeout long-lived connections (D6).

### D6 — Fly `http_service` tuned for long-lived WebSockets

Fly's proxy handles WebSocket upgrades by default, but idle-connection handling matters for a turn-based game where a connection can sit quiet between turns. Keep the HTTP service simple, rely on the client's reconnect (Phase 4 D3) as the safety net for any proxy-level idle drop, and use a cheap `GET /health` (Phase 0) as the Machine health check — **not** a WebSocket check.

### D7 — TMDB key invariant holds end-to-end

The TMDB key lives only as a Fly secret on the server Machine (same invariant as the Kotlin project: never in a client bundle). The web app never sees it — all TMDB access is the server's `/movies|people/...` proxy. Verify the built web bundle contains no TMDB key (grep the `dist/` output) as a release gate.

---

## Part 1 — Containerize the server

### `Dockerfile` (repo root or `server/`)

A multi-stage-ish uv build. uv provides a prebuilt image with the toolchain.

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Install deps first (layer-cached unless lockfile changes)
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App source + migrations
COPY server/app ./app
COPY server/migrations ./migrations
COPY server/alembic.ini ./alembic.ini

# Install the project itself
RUN uv sync --frozen --no-dev

EXPOSE 8080
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Notes:
- `--no-dev` excludes test/lint tooling from the production image (smaller, fewer CVEs).
- `--frozen` fails if `uv.lock` is stale — the same guarantee CI uses.
- Deps copied and synced before source so a code-only change doesn't re-resolve dependencies (Docker layer cache).
- Port 8080 matches `fly.toml`'s `internal_port`.

`.dockerignore` (repo root) to keep the image lean and avoid leaking local state:

```
**/.venv
**/__pycache__
**/.mypy_cache
**/.ruff_cache
**/.pytest_cache
web
packages
node_modules
local.properties
*.db
```

(`web`/`packages` are not part of the server image — they deploy to Vercel.)

---

## Part 2 — `fly.toml`

Create at repo root (or `server/`; keep it next to the Dockerfile context).

```toml
app = "bacons-law"
primary_region = "iad"          # pick the region closest to your testers

[build]
  dockerfile = "Dockerfile"

[deploy]
  # D2: migrations run once per deploy, before traffic shifts.
  release_command = "uv run alembic upgrade head"

[env]
  # non-secret defaults; secrets (TMDB_API_KEY, REDIS_URL, DATABASE_URL, WEB_ORIGIN) via `fly secrets`
  PORT = "8080"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false     # D1: never scale to zero — stateful WS + in-process registry
  auto_start_machines = true
  min_machines_running = 1       # D1: exactly one always-on Machine in v1

  [[http_service.checks]]
    method = "get"
    path = "/health"             # D6: cheap HTTP check, NOT a websocket check
    interval = "15s"
    timeout = "2s"

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"               # FastAPI + one Redis/PG pool; bump if RSS grows
```

The `release_command` runs in a one-off Machine with the deployed image and the app's secrets, so `DATABASE_URL` is available to Alembic exactly as it is to the app.

---

## Part 3 — Provision infra and deploy

Run from the repo root. (These are the human-run steps; if you're offline, this is the reference for when you're back online — nothing here is automatable without Fly API access.)

```bash
# 0) one-time: auth + app
fly auth login
fly apps create bacons-law

# 1) Postgres (Fly Postgres) — attaches DATABASE_URL secret automatically
fly postgres create --name bacons-law-db --region iad
fly postgres attach bacons-law-db --app bacons-law
#    `attach` sets DATABASE_URL on the app. Confirm it uses the asyncpg driver:
#    must be postgresql+asyncpg://...  — if attach sets a bare postgresql:// URL,
#    override it (see Risk flags):
fly secrets set DATABASE_URL="postgresql+asyncpg://<user>:<pwd>@<host>:5432/<db>" --app bacons-law

# 2) Redis (Upstash on Fly) — prints a redis:// URL
fly redis create --name bacons-law-redis --region iad
fly secrets set REDIS_URL="redis://<...>" --app bacons-law

# 3) App secrets
fly secrets set TMDB_API_KEY="<your-tmdb-key>" --app bacons-law
fly secrets set WEB_ORIGIN="https://bacons-law.vercel.app" --app bacons-law

# 4) Deploy (builds Dockerfile, runs release_command = alembic upgrade head, then serves)
fly deploy --app bacons-law

# 5) Smoke test the deployed API
curl https://bacons-law.fly.dev/health           # -> {"status":"ok"}
curl -X POST https://bacons-law.fly.dev/rooms \
  -H 'content-type: application/json' -d '{"displayName":"Smoke"}'   # -> {code, token, playerIndex}
```

Setting any secret triggers a rolling restart; the app re-reads them in the lifespan (Phase 3). If `alembic upgrade head` fails in the release command, the deploy aborts and the prior version (if any) keeps running — check `fly logs`.

---

## Part 4 — Deploy the web app (Vercel, D4)

The web build is a static SPA. Two coupling points: the API base URL and SPA-fallback routing.

### Build config

Vercel auto-detects Vite. Project settings:
- **Root directory:** `web`
- **Build command:** `pnpm --filter web build` (run from repo root) or `pnpm build` with root = `web` — confirm the monorepo workspace install resolves `@bacons-law/game-client`. If Vercel's install doesn't pick up the workspace, set install command to `pnpm install` at the repo root and build command to `pnpm --filter web... build` (build the package + web).
- **Output directory:** `web/dist`
- **Env var:** `VITE_API_BASE_URL = https://bacons-law.fly.dev` (Production). The client derives `wss://bacons-law.fly.dev` from it (D5).

### SPA routing

The app uses client-side routes (`/rooms/:code`, `/history/:id`). A static host returns 404 on a deep-link refresh unless it rewrites all paths to `index.html`. Add `web/vercel.json`:

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

### Close the CORS loop

The Vercel production URL must match the server's `WEB_ORIGIN` secret (Part 3, step 3). Set it after the first Vercel deploy reveals the real domain, or set both to the known `https://bacons-law.vercel.app` up front. Preview deploys have per-branch URLs — either add them to `WEB_ORIGIN` (comma-separated, Phase 4 CORS reads `.split(",")`) or test only against the production URL.

---

## Part 5 — Two-device playtest (the acceptance test)

This is the initiative's done-when. Two physical devices, two networks (ideally one on cellular to prove it's not LAN-dependent), public internet only.

### Checklist

1. **Device A** opens `https://bacons-law.vercel.app`, creates a room, reads the room code aloud.
2. **Device B** opens the same URL, joins with the code + a name. Device A sees Device B appear (phase `waiting` → `playing`).
3. Play a full alternating chain: A plays an actor, B plays a movie featuring that actor, A plays an actor in that movie, … Each move appears on **both** devices within a second or two.
4. **Invalid move:** one player submits a movie that doesn't feature the previous actor (or a repeat). Both devices land on game-over; the **other** player is shown as winner; the losing move is named.
5. **Reconnect:** mid-game, lock Device B's phone / background the tab, then return. It resumes to the current chain (token-based `resume`, Phase 4 D3) without losing the game.
6. **Forfeit path:** in a fresh room, one player taps "Give up". Both see game-over; `losing_move` absent; the other player wins.
7. **History:** both devices open `/history`. The finished game(s) appear, newest first. Open one → the full chain renders, winner correct.

### What each step proves

| Step | Validates |
| --- | --- |
| 1–2 | `POST /rooms`, WS connect/auth, broadcast, deployed CORS + `wss://` |
| 3 | server-side engine validation, TMDB credits fetch on movie moves, live broadcast |
| 4 | R2–R6 over the wire; winner/loser determination; game-over broadcast |
| 5 | Redis-backed state survives a dropped socket; token `resume` snapshot |
| 6 | forfeit path; one-shot Postgres write on a non-error end |
| 7 | Postgres write actually landed; history read endpoints; SPA deep-link routing |

If all seven pass against the deployed stack, the rewrite initiative's acceptance criterion is met.

---

## Verification (pre-playtest gates)

Before the human playtest, confirm the boxes that don't need two people:

```bash
# Deployed API up and migrated
curl https://bacons-law.fly.dev/health
fly logs --app bacons-law            # release_command shows "alembic upgrade head ... OK"
fly ssh console --app bacons-law -C "uv run alembic current"   # -> 0001 (head)

# TMDB key is NOT in the web bundle (D7)
pnpm --filter web build
grep -r "<the-tmdb-key-prefix>" web/dist && echo "LEAK" || echo "clean"

# Single Machine (D1)
fly status --app bacons-law          # exactly one Machine, started
```

---

## Deliverable → file/command mapping

| Deliverable | Artifact |
| --- | --- |
| Server container | `Dockerfile`, `.dockerignore` |
| Fly app config | `fly.toml` |
| Migrations on deploy | `[deploy] release_command` in `fly.toml` |
| Redis | `fly redis create` → `REDIS_URL` secret |
| Postgres | `fly postgres create` + `attach` → `DATABASE_URL` secret |
| TMDB key | `fly secrets set TMDB_API_KEY` |
| CORS allow-list | `WEB_ORIGIN` secret ↔ Vercel URL |
| Web host | Vercel project, `web/vercel.json`, `VITE_API_BASE_URL` |

---

## Commit sequence

1. `chore: add server Dockerfile and dockerignore`
2. `chore: add fly.toml with alembic release command`
3. `chore: add vercel config for web spa routing`

The Fly/Vercel provisioning and secret-setting (Part 3, Part 4) are operational steps, not commits — they live in this doc and in the platform dashboards, not the repo. Update [DECISIONS.md](DECISIONS.md) (or the rewrite plan's decision log) with the Vercel choice (D4) once made.

---

## Risk flags

- **Single Machine is load-bearing (D1).** Scaling to >1 Machine silently breaks cross-client broadcasts — connections on Machine A can't be reached from Machine B's in-process registry. Keep `min_machines_running = 1` / `auto_stop_machines = false` until the deferred Redis-pub/sub fan-out is built. Document this in `fly.toml`.
- **`DATABASE_URL` driver prefix.** `fly postgres attach` may set a bare `postgresql://` URL. SQLAlchemy's async engine needs `postgresql+asyncpg://`. If the app fails at startup with a sync-driver or "dialect" error, override the secret to the `+asyncpg` form. The Alembic env reads the same URL (Phase 3) — it must also be the async form for `run_sync` to work.
- **Release command failures abort the deploy.** A bad migration fails `alembic upgrade head` and the new version never serves. Good (fail-closed), but means a broken migration blocks deploys — test `alembic upgrade head` against a throwaway Postgres before deploying.
- **WebSocket idle drops behind the Fly proxy (D6).** A turn-based game has quiet stretches; a proxy idle-timeout could drop the socket mid-game. The client's auto-reconnect + `resume` (Phase 4 D3) is the designed safety net — verify step 5 of the playtest actually exercises a real drop (background long enough to trip any timeout), not just a clean reload.
- **CORS/origin mismatch (D5).** The single most likely "it works locally, fails deployed" bug: `WEB_ORIGIN` not matching the actual Vercel URL → every REST call (search, create room, history) fails with a CORS error while WS still connects. Symptom: the room connects but search returns nothing. Set `WEB_ORIGIN` to the exact production origin (scheme + host, no trailing slash).
- **Redis TTL vs. playtest pacing.** Rooms TTL at 24h (Phase 3) and refresh on activity — fine. But an idle room during a long debugging session won't expire mid-test. Not a risk for the playtest; noted so the 24h number isn't surprising if you inspect Redis.
- **Cost of always-on.** One pinned `shared-cpu-1x`/512mb Machine plus managed Redis/Postgres runs ~continuously (no scale-to-zero, by design). This is the accepted trade of choosing persistent-connection hosting over serverless — modest at hobby scale, but non-zero unlike Cloud Run's idle-free model. Stop the Machine (`fly machine stop`) between playtests if cost matters.
- **TMDB key in the bundle (D7).** A regression that reads the key client-side (e.g., a "temporary" direct TMDB call) would ship it in `web/dist`. The grep gate in Verification catches it; keep it in the release checklist.
```
