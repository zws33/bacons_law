# Bacon's Law Roadmap

## Project Summary

A two-player mobile trivia game based on "Six Degrees of Kevin Bacon." Players pass a phone back and forth, taking turns naming movies and actors. Each answer must connect to the previous one — the actor must have been in that movie, or the movie must feature that actor. The app validates every move using TMDB data. First player who can't name a valid connection loses.

**Current state:** Existing Kotlin/Compose codebase with TMDB API integration (search + credits) and a game state machine. The game logic and UI are not yet connected. The existing code is a starting point — reusable where it serves the MVP, replaceable where it doesn't.

See [docs/GAME_SPEC.md](docs/GAME_SPEC.md) for the full game rules.
See [docs/DECISIONS.md](docs/DECISIONS.md) for key technical and product decisions.

---

## Phase 1: Playable MVP

**Goal:** Two people can pass a phone and play a complete round of Bacon's Law. The app validates every move. Nothing more.

### Game Flow
- [ ] Start screen — enter two player names, start game
- [ ] Player 1 searches for and selects a starting actor
- [ ] Prompt screen — shows current player, the previous chain entry, and what type of move is needed ("Name a movie **[Actor]** was in")
- [ ] Search and select — current player searches, picks from results
- [ ] Validation — app checks the connection via TMDB credits. Valid: add to chain, switch turns. Invalid: game over.
- [ ] Repeat detection — reject moves that reuse an actor or movie already in the chain
- [ ] Forfeit — "I can't answer" button that concedes the round
- [ ] Game over screen — show winner, display the full chain, play again button

### Technical
- [ ] Evaluate existing `:core` game engine against game spec — adapt or rewrite
- [ ] Stand up `:backend` Ktor module with three proxy endpoints: movie search, person search, movie credits
- [ ] Deploy `:backend` to Cloud Run with TMDB API key stored in Google Secret Manager
- [ ] Wire `:app` Repository to `:backend` endpoints (not TMDB directly)
- [ ] Wire TMDB credits API (via `:backend`) to move validation
- [ ] Compose navigation for game flow (start → play → game over)
- [ ] Update Gradle/Kotlin/AGP to current stable versions
- [ ] TMDB API key must not be embedded in any client binary — all TMDB calls go through `:backend`

### Done When
- Two players can complete a full game by passing the phone
- Every move is validated against TMDB data
- Invalid moves and repeats end the game correctly
- The chain is visible throughout the game

---

## Phase 2: Polish and Publish

**Goal:** Good enough for the Play Store. Not perfect — shippable.

- [ ] Onboarding — brief rules explanation for first-time players
- [ ] UI polish — movie posters / actor photos from TMDB, chain visualization, turn transitions
- [ ] Error handling — network failures, empty search results, API rate limits surfaced to the user
- [ ] Loading states during API calls
- [ ] TMDB attribution (required by API terms of use)
- [ ] Play Store listing — icon, screenshots, description, privacy policy
- [ ] Publish — internal testing track, then production

---

## Phase 3: Game Depth

**Goal:** Mechanics that make the game more engaging, informed by real play experience.

Candidates (prioritize based on what feels missing after playing):
- [ ] Single-player quiz-master mode — app prompts, you respond
- [ ] Time limits per turn
- [ ] Pass / miss tolerance mechanics
- [ ] Difficulty settings (popular vs. obscure movies/actors)
- [ ] Game history and statistics
- [ ] Share results ("We built a chain of 12 connections!")

---

## Phase 4: Online Multiplayer (Ktor Backend)

**Goal:** Play remotely against friends on separate devices. The `:backend` service evolves from a stateless TMDB proxy to an authoritative game server.

- [ ] Game session management — create, join, and persist match state in `:backend`
- [ ] Move validation moves server-side — clients submit intents, backend validates and advances state
- [ ] WebSocket or SSE — real-time state push to connected clients
- [ ] Android client updates — connect to remote game session
- [ ] Persistence — game history, player accounts

**T-shape value:** Server-side Kotlin, coroutine-based concurrency, real-time communication, API design, deployment on Cloud Run.

---

## Phase 5: Cross-Platform

- [ ] iOS client via Kotlin Multiplatform — share `:core` game engine and network layer with the Android app
- [ ] Web client (Compose for Web) against the Ktor backend
