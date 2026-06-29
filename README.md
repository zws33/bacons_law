# Bacon's Law

A real-time, two-player trivia game based on "Six Degrees of Kevin Bacon." Two players on **separate
devices** take turns naming movies and actors to build a chain of connections. A Kotlin/Ktor server
validates every move against a precomputed actor↔movie graph. The first player who can't name a valid
connection loses.

## How It Works

1. Player 1 picks a starting actor
2. Player 2 names a movie that actor was in
3. Player 1 names an actor from that movie
4. Keep going — the chain grows: Actor → Movie → Actor → Movie → …
5. The server validates every connection. First wrong answer loses.

The fun is in the pressure: you don't control what the other player picks, so you never know what's
coming next.

## Architecture

Validation is the design crux, and the key insight (see [docs/CASE_STUDY.md](docs/CASE_STUDY.md)) is
that it should be **precomputed, not looked up per turn**:

- An offline **Python ETL** builds a bipartite movie↔actor graph from **CC0 Wikidata** data
  (`movie_id → set(actor_id)`, `actor_id → set(movie_id)`), capped to top-billed cast.
- The **Kotlin/Ktor server** loads that graph **read-only, in-process** at boot and validates a move
  with an O(1) set-membership check — no per-turn external API call.
- The pure **Kotlin `:core` engine** owns the rules; **Redis** holds live per-room state for
  multi-device, server-authoritative play.

The graph and the validation logic must stay in the same process — that co-location is what makes
validation cheap.

## Tech Stack

- **Kotlin / Ktor** — authoritative game server (WebSocket rooms, in-process graph)
- **Kotlin `:core`** — pure game engine (state machine, validation, turn management)
- **Python** — offline ETL building the Wikidata graph artifact
- **Redis** — live per-room state
- **Fly.io** — single long-lived instance (required for persistent WebSockets)
- **Kotlin / Jetpack Compose** — Android client (secondary)

## Project Structure

The root is stack-agnostic; each implementation lives in its own self-contained top-level directory.

```
bacons-law/
├── docs/          # Engine spec, case study, decision log; docs/python/ archives the prior showcase
├── kotlin/        # Self-contained Gradle project — the Kotlin implementation
│   ├── core/      #   Pure Kotlin game engine — state machine, validation, turn management
│   ├── backend/   #   Ktor server — graph-backed session server (being rebuilt from a proxy)
│   └── app/       #   Android/Compose client (secondary)
├── etl/           # Python — offline Wikidata graph build (planned)
└── ROADMAP.md     # Phased development plan
```

## Status

**Pivoting** to the architecture above. The `:core` engine is reused as-is; `:backend` is being
rebuilt from a TMDB proxy into the graph-backed server. Two prior efforts are preserved as reference:
the Kotlin/Compose Android client and a Python/FastAPI showcase (branch `fullstack-py-ts-rewrite`, tag
`python-fastapi-showcase`). See [ROADMAP.md](ROADMAP.md).

## Setup

No API keys are required — the actor↔movie data comes from CC0 Wikidata, built offline by the ETL.

- Game logic: `./gradlew :core:test`
- (Server and ETL setup are documented as those phases land — see [ROADMAP.md](ROADMAP.md).)

## Documentation

- [Engine Spec](docs/GAME_SPEC_V2.md) — authoritative rules and state machine
- [Case Study](docs/CASE_STUDY.md) — the system-design reasoning behind this architecture
- [Decision Log](docs/DECISIONS.md) — key technical and product decisions with rationale
- [Roadmap](ROADMAP.md) — phased development plan

## Data & License

Actor↔movie data is sourced from [Wikidata](https://www.wikidata.org/), released under
[CC0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain) — no attribution required
and no restriction on commercial or AI use.
