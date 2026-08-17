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

Validation is the design crux, and the key insight (see
[the system-design case study](docs/investigations/000-system-design-case-study.md)) is
that it should be **precomputed, not looked up per turn**:

- An offline **Python ETL** builds a bipartite movie↔actor graph from **CC0 Wikidata** data
  (`movie_qid → set(actor_qid)`, `actor_qid → set(movie_qid)`), capped to top-billed cast.
- That graph is loaded into **Postgres**, in its own schema, next to authoritative game state
  ([ADR 026](docs/DECISIONS.md)). A move is validated by one indexed lookup — no per-turn external
  API call, ever.
- A **pure round engine** owns the rules, specified by
  [docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md). It never reads the graph itself; the
  session layer passes the cast in as data.

**The insight is that validation is precomputed, not that it is in memory.** The project held those
together for a while — the graph used to be loaded read-only into the server's process, and the
engine/data seam was forbidden to cross a network hop. That constraint protected a latency budget that
[ADR 018](docs/DECISIONS.md) and [ADR 025](docs/DECISIONS.md) established this game does not have: a
turn takes minutes to days. Co-location cost a 21 MB artifact shipped to every instance, a resident
memory footprint that set the instance size, and a fleet redeploy for every graph version bump. Moving
the graph into the store removes all three.

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
- **TypeScript on Node, Fastify** — the server ([ADR 025](docs/DECISIONS.md)). Not written yet.
- **Web** — the primary client ([ADR 023](docs/DECISIONS.md)), its own top-level directory. Native is a
  showcase follow-up. Not written yet.
- **Supabase** — Postgres for game state *and* the graph, plus the identity provider
  ([ADRs 026 and 027](docs/DECISIONS.md)). The server holds the service key and stays authoritative;
  clients never touch the database. Identity is a JWT verified against the provider's JWKS
  ([ADR 022](docs/DECISIONS.md)).

**Open — nothing below is chosen:**

- **Hosting.** Open on cost and operational simplicity; cold start is measured and is not an obstacle.
  One constraint: the server must run in the same region as the database, because typeahead is the
  only latency-sensitive path and it now takes a round trip.

## Project Structure

The root is stack-agnostic; each implementation lives in its own self-contained top-level directory.

```
bacons-law/
├── docs/          # Decision log, engine + match specs, history note
│   └── investigations/   #   Records, never rules — case study + investigation write-ups
└── etl/           # Python — offline Wikidata graph build
```

`server/` (TypeScript) and the web client are decided but not started, and will be sibling top-level
directories with their own toolchains.

## Status

**The ETL is the settled part** — a working pipeline that builds the graph artifact the game engine
validates moves against. It is the only fixed contract in the repo. The first full-range artifact
(`v1`, 1925–2026) is built: **47,624 movies, 89,074 actors, 456,129 edges, 21MB**. `data/` is
gitignored, so the artifact is not in this tree — see [etl/README.md](etl/README.md) to build it.

**The rules are the second settled part.** [ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md) and
[MATCH_CONFORMANCE.md](docs/MATCH_CONFORMANCE.md) specify the round engine and the match layer as
numbered rules plus a conformance suite, language-agnostic and authoritative over any implementation.
They are what made the stack a reversible choice.

**The server and the client do not exist yet.** The stack, the client, identity, and storage are
decided (ADRs 022, 023, 025, 026, 027); hosting is the only one left, and its constraints are collected
in **Open: Hosting** at the end of the [decision log](docs/DECISIONS.md).

Two prior efforts are preserved as tags, not as directories: the Kotlin/Compose Android client and its
Ktor proxy (tag `kotlin-android-mvp`) and a Python/FastAPI showcase (branch `fullstack-py-ts-rewrite`,
tag `python-fastapi-showcase`). Neither is a starting point — see [History](docs/HISTORY.md).

## Setup

No API keys are required — the actor↔movie data comes from CC0 Wikidata, built offline by the ETL.

- ETL: see [etl/README.md](etl/README.md). It is the only buildable component in the tree.

## Documentation

- [Engine Conformance Spec](docs/ENGINE_CONFORMANCE.md) — **the round engine's spec of record.** Rules
  R1–R17 plus a numbered conformance suite, language- and framework-agnostic
- [Match Conformance Spec](docs/MATCH_CONFORMANCE.md) — **the match layer's spec of record.** Rules
  M1–M16 plus a conformance suite: strikes, removal, standings, opener rotation
- [Decision Log](docs/DECISIONS.md) — key technical and product decisions with the reasoning behind
  them; read for the *why*, not as a set of commitments. **ADR 018 is the most consequential recent
  one** — it amends 008, 011, and 012 on transport, hosting, and modes
- [Case Study](docs/investigations/000-system-design-case-study.md) — the system-design reasoning behind this architecture. Its §2, §5,
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
