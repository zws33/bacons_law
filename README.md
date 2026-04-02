# Bacon's Law

A two-player mobile trivia game based on "Six Degrees of Kevin Bacon." Players pass a phone back and forth, naming movies and actors to build a chain of connections. Every move is validated in real-time using [TMDB](https://www.themoviedb.org/) data. The first player who can't name a valid connection loses.

## How It Works

1. Player 1 picks a starting actor
2. Player 2 names a movie that actor was in
3. Player 1 names an actor from that movie
4. Keep going — the chain grows: Actor → Movie → Actor → Movie → ...
5. The app validates every connection. First wrong answer loses.

The fun is in the pressure: you don't control what the other player picks, so you never know what's coming next.

## Tech Stack

- **Kotlin** / **Jetpack Compose** — UI and application layer
- **TMDB API** — Movie and actor data, cast validation
- **Coroutines** — Async API calls
- **Multi-module architecture** — `:app` (presentation + data) and `:core` (game engine)

## Project Structure

```
bacons-law/
├── app/          # Android app — Compose UI, TMDB integration, ViewModels
├── core/         # Game engine — state machine, move validation, turn management
├── docs/         # Game spec, architecture decisions
└── ROADMAP.md    # Development plan
```

## Status

**In development.** The game engine and TMDB integration exist independently — currently wiring them together into a playable game loop. See [ROADMAP.md](ROADMAP.md) for the full plan.

## Setup

1. Clone the repo
2. Get a [TMDB API key](https://developer.themoviedb.org/docs/getting-started)
3. Add your key to `local.properties`:
   ```
   TMDB_API_KEY=YOUR_KEY_HERE
   ```
4. Build and run via Android Studio

## Documentation

- [Game Spec](docs/GAME_SPEC.md) — Rules and mechanics
- [Decision Log](docs/DECISIONS.md) — Key technical and product decisions with rationale
- [Roadmap](ROADMAP.md) — Phased development plan

## License

This project uses data from [The Movie Database (TMDB)](https://www.themoviedb.org/). This product uses the TMDB API but is not endorsed or certified by TMDB.
