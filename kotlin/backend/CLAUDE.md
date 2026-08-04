# `:backend` — environment

> **Provisional.** The current source is still the TMDB proxy this module started as. It — and the
> choice of Kotlin/Ktor for the server at all — is subject to change or deletion at the planning
> session. Don't preserve its shape for its own sake. See the root `AGENTS.md`.

The server needs `DATABASE_URL` (Postgres — authoritative game state) and `REDIS_URL` (presence,
pub/sub broadcast, hot-game cache). In production these are injected via `fly secrets`; locally,
export them in the environment.

There is no TMDB key — validation data comes from CC0 Wikidata, built offline by `etl/`. Do not
reintroduce a per-turn movie-API dependency.
