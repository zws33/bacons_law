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

Validation is the design crux, and the key insight is that it should be **precomputed, not looked up per turn**:

- An offline **Python ETL** builds a bipartite movie↔actor graph from **CC0 Wikidata** data
  (`movie_qid → set(actor_qid)`, `actor_qid → set(movie_qid)`), capped to top-billed cast.
- A **pure round engine** owns the rules, specified by [docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md). It never reads the graph itself; the session layer passes the cast in as data.

## Tech Stack

**Settled:**

- **Python** — offline ETL building the Wikidata graph artifact. The only fixed contract in the repo.
- **TypeScript on Node, Fastify** — the server. Not written yet.
- **Web** — the primary client, its own top-level directory. Native is a
  showcase follow-up. Not written yet.
- **Supabase** — Postgres for game state *and* the graph, plus the identity provider. The server holds the service key and stays authoritative; clients never touch the database. Identity is a JWT verified against the provider's JWKS.

**Open — nothing below is chosen:**

- **Hosting.** Open on cost and operational simplicity; cold start is measured and is not an obstacle.
  One constraint: the server must run in the same region as the database, because typeahead is the
  only latency-sensitive path and it now takes a round trip.

[ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md) and [MATCH_CONFORMANCE.md](docs/MATCH_CONFORMANCE.md) specify the round engine and the match layer as numbered rules plus a conformance suite, language-agnostic and authoritative over any implementation.

## Documentation

- [Engine Conformance Spec](docs/ENGINE_CONFORMANCE.md) — **the round engine's spec of record.** Rules
  R1–R17 plus a numbered conformance suite, language- and framework-agnostic
- [Match Conformance Spec](docs/MATCH_CONFORMANCE.md) — **the match layer's spec of record.** Rules
  M1–M16 plus a conformance suite: strikes, removal, standings, opener rotation
- [ETL](etl/README.md) — the offline graph build

## Data & License

Actor and movie data is sourced from [Wikidata](https://www.wikidata.org/), released under [CC0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain) — no attribution required and no restriction on commercial or AI use.
