# Bacon's Law

A trivia game based on "Six Degrees of Kevin Bacon." **Two or more players on separate devices** take
turns naming movies and actors to build a chain of connections. Play is **async ("correspondence")** —
move when you can, get notified when it's your turn, with a per-turn deadline. A server validates every
move against a precomputed actor↔movie graph.

## How It Works

1. A player opens with an actor or a movie
2. The next player names a movie that actor was in
3. The next names an actor from that movie
4. Keep going — the chain grows: Actor → Movie → Actor → Movie → …
5. The server validates every connection

A **round** ends the moment someone can't answer — that player is the round's loser. A **match** is a
series of rounds in which players accumulate strikes, lowest score best. There is no miss tolerance
inside a round: the first failure ends it.

The fun is in the pressure: you don't control what the other players pick, so you never know what's
coming next.

## Architecture

Validation is the design crux, and the key insight (see [docs/CASE_STUDY.md](docs/CASE_STUDY.md)) is
that it should be **precomputed, not looked up per turn**:

- An offline **Python ETL** builds a bipartite movie↔actor graph from **CC0 Wikidata** data
  (`movie_qid → set(actor_qid)`, `actor_qid → set(movie_qid)`), capped to top-billed cast.
- The **server** loads that graph **read-only, in-process** at boot and validates a move with an O(1)
  set-membership check — no per-turn external API call.
- A **pure round engine** owns the rules, specified by
  [docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md). A **durable store** holds authoritative
  game state — it must survive restarts and span days. Which store is an open planning question.

The graph and the validation logic must stay in the same process — that co-location is what makes
validation cheap.

The second design crux is one the project got wrong first and corrected
([ADR 018](docs/DECISIONS.md)): **the game is turn-based, and real-time is a time control rather than
an architecture.** Nothing in the rules is decided by reaction time, so moves go over ordinary
request/response and an opponent learns of one by polling plus push — no WebSockets, no presence
service, no broadcast channel, and no single-instance constraint. A live chess clock is deferred, and
because a turn deadline is stored as a duration rather than a mode, adding one later is a different
number, not a second system.

## Tech Stack

**Settled:**

- **Python** — offline ETL building the Wikidata graph artifact. The only fixed contract in the repo.

**Open — decided in an upcoming planning session, nothing below is chosen:**

- **Server language and framework.** The tree holds a Kotlin/Ktor server and a pure Kotlin `:core`
  engine; both are prototypes, not commitments.
- **Durable store** for authoritative game state. Prior choices were withdrawn to avoid biasing this
  decision. There is no presence/broadcast layer to choose — see [ADR 018](docs/DECISIONS.md).
- **Client.** The tree holds an unmaintained Android/Compose app built for a dropped design.
- **Hosting.** Wide open. An earlier revision of this file required a single long-lived instance;
  [ADR 018](docs/DECISIONS.md) removed that. The graph is read-only and identical on every instance, so
  it constrains **cold start**, not instance count — and that is a measurement, not a ruling.

## Project Structure

The root is stack-agnostic; each implementation lives in its own self-contained top-level directory.

```
bacons-law/
├── docs/          # Case study, decision log, engine spec, and a history note on prior efforts
├── kotlin/        # Self-contained Gradle project — the Kotlin implementation
│   ├── core/      #   Pure Kotlin game engine — state machine, validation, turn management
│   ├── backend/   #   Ktor server — graph-backed session server (being rebuilt from a proxy)
│   └── app/       #   Android/Compose client (secondary)
└── etl/           # Python — offline Wikidata graph build
```

## Status

**The ETL is the settled part** — a working pipeline that builds the graph artifact the game engine
validates moves against. It is the only fixed contract in the repo. The first full-range artifact
(`v1`, 1925–2026) is built: **47,624 movies, 89,074 actors, 456,129 edges, 21MB**. `data/` is
gitignored, so the artifact is not in this tree — see [etl/README.md](etl/README.md) to build it.

Everything else is provisional. The engine, server, and client, the persistence and session design
sketched above, and the choice of language and framework will all be reevaluated in a planning
session; the Kotlin modules in this tree are where that work currently stands, not a commitment.
[docs/DECISIONS.md](docs/DECISIONS.md) (ADRs 008–013) records the reasoning that got the project
here — read it for the *why*, which holds, rather than as a set of commitments.

Two prior efforts are preserved as reference, not maintained: the Kotlin/Compose Android client and a
Python/FastAPI showcase (branch `fullstack-py-ts-rewrite`, tag `python-fastapi-showcase`).

## Setup

No API keys are required — the actor↔movie data comes from CC0 Wikidata, built offline by the ETL.

- Game logic: `./gradlew :core:jvmTest` (from `kotlin/`)
- ETL: see [etl/README.md](etl/README.md)

## Documentation

- [Engine Conformance Spec](docs/ENGINE_CONFORMANCE.md) — **the round engine's spec of record.** Rules
  R1–R15 plus a numbered conformance suite, language- and framework-agnostic. Authoritative over
  `kotlin/core/.../GameEngine.kt`, which is prototype code the spec records divergences from
- [Decision Log](docs/DECISIONS.md) — key technical and product decisions with the reasoning behind
  them; read for the *why*, not as a set of commitments. **ADR 018 is the most consequential recent
  one** — it amends 008, 011, and 012 on transport, hosting, and modes
- [Case Study](docs/CASE_STUDY.md) — the system-design reasoning behind this architecture. Its §2, §5,
  and §6 assume a WebSocket transport the project has since dropped; they are kept as dated record with
  inline superseding markers
- [ETL](etl/README.md) — the offline graph build
- [Agents Guide](AGENTS.md) — repository layout, conventions, and architecture boundaries
- [History](docs/HISTORY.md) — the two prior efforts and why they ended; reference, not guidance

The phased roadmap was retired pending a fresh planning pass — nothing in the tree tracks live status.

## Data & License

Actor↔movie data is sourced from [Wikidata](https://www.wikidata.org/), released under
[CC0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain) — no attribution required
and no restriction on commercial or AI use.
