# Bacon's Law

A two-player trivia game based on "Six Degrees of Kevin Bacon." Players take turns naming movies and
actors to build a chain of connections. Every move is validated in real-time using
[TMDB](https://www.themoviedb.org/) data. The first player who can't name a valid connection loses.

## How It Works

1. Player 1 picks a starting actor
2. Player 2 names a movie that actor was in
3. Player 1 names an actor from that movie
4. Keep going — the chain grows: Actor → Movie → Actor → Movie → ...
5. Every connection is validated. First wrong answer loses.

The fun is in the pressure: you don't control what the other player picks, so you never know what's
coming next.

## Tech Stack

- **Python** / **FastAPI** — backend API, game engine, TMDB proxy
- **TypeScript** — web client (in progress)
- **React Native** — mobile client (planned)
- **TMDB API** — movie and actor data, cast validation

## Project Structure

```
bacons-law/
├── server/           # Python backend — FastAPI, game engine, TMDB proxy
│   ├── app/          # Application code (routes, engine, models)
│   └── tests/        # pytest test suite
├── packages/
│   └── game-client/  # TypeScript web client
├── docs/             # Game spec, architecture decisions, implementation plans
└── ROADMAP.md        # Phased development plan
```

## Status

**In development.** The Python game engine and backend scaffolding are built. Currently implementing
the TMDB proxy endpoints (Phase 2). See [ROADMAP.md](ROADMAP.md) for the full plan.

## Setup

### Backend

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

1. Get a [TMDB API key](https://developer.themoviedb.org/docs/getting-started)
2. Set the key in your environment:
   ```
   export TMDB_API_KEY=your_key_here
   ```
3. Install dependencies and run the server:
   ```bash
   cd server
   uv sync
   uv run uvicorn app.main:app --reload
   ```

### Web Client

Requires [pnpm](https://pnpm.io/).

```bash
pnpm install
pnpm --filter @bacons-law/game-client typecheck
```

### Running Tests

```bash
cd server
uv run pytest
```

## Documentation

- [Game Spec](docs/GAME_SPEC.md) — Rules and mechanics
- [Decision Log](docs/DECISIONS.md) — Key technical and product decisions with rationale
- [Roadmap](ROADMAP.md) — Phased development plan

## License

This project uses data from [The Movie Database (TMDB)](https://www.themoviedb.org/). This product
uses the TMDB API but is not endorsed or certified by TMDB.
