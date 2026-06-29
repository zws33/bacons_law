# Bacon's Law — Game Spec (MVP)

> **Superseded for the engine by [GAME_SPEC_V2.md](GAME_SPEC_V2.md).** V2 is the authoritative spec
> for the pure engine (state transitions, validation, end conditions). This document is retained for
> **product intent and out-of-scope decisions**. Note its "local (pass-the-phone)" setup is itself
> superseded — multi-device, server-authoritative play is now a core requirement (see the decision
> log in [DECISIONS.md](DECISIONS.md)).

This document is a historical reference for game behavior and product intent.

## Concept

Two players take turns naming movies and actors, building a chain of connections. Each entry must be connected to the previous one — the actor must have appeared in the previous movie, or the movie must feature the previous actor. The first player who can't name a valid connection loses.

## Game Loop

### Setup

- Two players, local (pass-the-phone).
- Player 1 searches for and selects a **starting actor**. This is the first link in the chain.

### Turns

Turns alternate between the two players. The move type alternates between **movie** and **actor**:

1. Player 1 selects a starting **actor**. (e.g., "Tom Hanks")
2. Player 2 is prompted: *"Name a movie Tom Hanks was in."* Player 2 searches, selects a **movie**. (e.g., "Cast Away")
3. Player 1 is prompted: *"Name an actor in Cast Away."* Player 1 searches, selects an **actor**. (e.g., "Helen Hunt")
4. Player 2 is prompted: *"Name a movie Helen Hunt was in."* ...and so on.

The chain grows: Actor → Movie → Actor → Movie → ...

### Move Validation

Every move is validated by the app using TMDB data:

- **Movie move:** The app checks whether the previously named actor appears in this movie's cast.
- **Actor move:** The app checks whether this actor appears in the previously named movie's cast.

If the connection is **valid**: the move is added to the chain and the turn passes to the other player.

If the connection is **invalid**: the current player loses. The game ends.

### No Repeats

An actor or movie that already appears in the chain cannot be used again. If a player selects a repeated entry, the move is rejected (same as an invalid connection — that player loses).

### End Conditions

The game ends when:

1. **Invalid move** — a player names an actor/movie that isn't connected to the previous entry.
2. **Repeat** — a player names an actor/movie already in the chain.
3. **Forfeit** — a player concedes (explicit "I can't answer" action).

The other player wins.

### Post-Game

- Display the full chain of connections.
- Show the winner.
- Option to play again.

## What Counts as a Valid Entity

### Movies

- Theatrical films and widely released streaming films.
- TV shows, shorts, and documentaries are **excluded** for MVP.
- The app uses TMDB search results — if TMDB returns it as a movie, it's valid.

### Actors / Cast

- Any credited cast member in TMDB's movie credits is valid.
- This includes voice roles.
- Uncredited roles (not listed in TMDB credits) are not valid — the app can't validate them.

### Canonical Identity

- The app uses TMDB IDs as the canonical identifier for both movies and actors. This avoids ambiguity around remakes, alternate titles, or actors with the same name.
- Players select from search results (which display title, year, and actor photo/name), so they're always choosing a specific entity, not typing a free-text guess.

## Explicitly Out of Scope (MVP)

These mechanics are not part of the MVP. They may be added in future versions:

- Time limits per turn
- Pass / skip mechanic
- Miss tolerance (multiple attempts per turn)
- Challenge flow (disputing the previous player's move)
- Scoring or point systems
- Game history / statistics
- Difficulty settings or obscurity filters
- Online multiplayer
- Single-player / quiz-master mode
