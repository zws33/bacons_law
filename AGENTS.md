# Agents Guide — Bacon's Law

A trivia game based on "Six Degrees of Kevin Bacon." Two or more players on separate devices take
turns naming movies and actors to build a chain of connections, each answer connecting factually to
the one before it. Play is **correspondence** — async, move-when-you-can, with a per-turn deadline. A
server owns authoritative game state and validates every move against a precomputed actor↔movie graph
held in Postgres alongside that state.

## Conventions

- **Commits:** Conventional commit format — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
