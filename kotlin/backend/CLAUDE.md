# `:backend` — environment

The server needs `DATABASE_URL` (Postgres — authoritative game state) and `REDIS_URL` (presence,
pub/sub broadcast, hot-game cache). In production these are injected via `fly secrets`; locally,
export them in the environment.

There is no TMDB key — validation data comes from CC0 Wikidata, built offline by `etl/`. Do not
reintroduce a per-turn movie-API dependency.
