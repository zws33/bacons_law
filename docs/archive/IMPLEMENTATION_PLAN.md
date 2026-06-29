# Phase 1 Implementation Plan

Build order and design decisions for the playable MVP. Reference [GAME_SPEC.md](GAME_SPEC.md) for rules and behavior.

## Status

| Step | Status |
|------|--------|
| Build toolchain | **Done** |
| 1. Game engine rewrite | **Done** |
| 2a. Backend proxy service | **Done** |
| 2b. TMDB data layer | **Done** |
| 3. Game flow UI | **Done** |
| 4. Integration | **Done** |
| 5. MVP Refinement | **Next** |

## Completed

### Build toolchain ✓
(as before)

### Game Engine Rewrite ✓
(as before)

### Backend Proxy Service ✓
- Ktor service in `:backend` proxies TMDB search and credits.
- Normalizes TMDB responses to domain models.
- TMDB API key is kept server-side.

### TMDB Data Layer ✓
- `:app` Repository uses Ktor Client to hit `:backend`.
- Fetches fully-populated `Move` objects (including `castIds`).

### Game Flow UI ✓
- Start, Play, and Game Over screens implemented in Compose.
- `SearchViewModel` manages game state and data flow.

### Integration ✓
- Game loop fully functional: Search -> Select -> Fetch -> Validate -> State Update.
- Playable "pass-the-phone" MVP.

---

## 5. MVP Refinement ← next

**Goal:** Polish the user experience and ensure robustness before Phase 2.

### Tasks
- [ ] **Search Debouncing:** Prevent API spam by waiting for a pause in typing.
- [ ] **Empty States:** Clearly show when search returns no results.
- [ ] **Error Handling:** Improve feedback for network failures and timeouts.
- [ ] **Loading States:** Provide visual feedback during movie credit fetching.

---

## 1. Game Engine Design

**Goal:** Pure Kotlin state machine that models the full game spec. No Android dependencies. Fully testable.

### Types

```kotlin
sealed class GameState {
  data class InProgress(
    val moves: List<Move>,
    val currentPlayer: Player,
  ) : GameState()

  data class GameOver(
    val winner: Player,
    val loser: Player,
    val chain: List<Move>,
    val losingMove: Move? = null
  ) : GameState()
}

sealed class Move {
  abstract val id: Int
  abstract val displayText: String

  data class Actor(override val id: Int, override val displayText: String) : Move()
  data class Movie(override val id: Int, override val displayText: String, val castIds: Set<Int>) : Move()
}

enum class Player { ONE, TWO }
```

### Engine API

```kotlin
interface GameEngine {
  fun startGame(move: Move): GameState.InProgress
  fun playMove(move: Move, state: GameState.InProgress): GameState
  fun forfeit(state: GameState.InProgress): GameState.GameOver
}

fun GameEngine(): GameEngine = DefaultGameEngine
```

**Key decision: `Move.Movie` carries `castIds`.** The engine validates connections using these IDs. The caller (ViewModel) is responsible for fetching these IDs from TMDB before submitting a move. This keeps the engine pure and testable without network mocks while encapsulating the validation logic.

---

## 2a. Backend Proxy Service ← next

**Goal:** A deployable Ktor service that proxies TMDB. The Android app calls this service for all TMDB data. TMDB credentials never leave the backend.

### Module structure

New Gradle module `:backend` in the monorepo. Depends on `:core` for domain types. No Android dependencies.

### Endpoints

| Endpoint | TMDB operation | Returns |
|----------|---------------|---------|
| `GET /movies/search?query=` | Movie search | List of `{id, title}` |
| `GET /people/search?query=` | Person search | List of `{id, name}` |
| `GET /movies/{id}/credits` | Movie credits | `{id, title, castIds: [Int]}` |

The credits endpoint returns a response that maps directly to a `Move.Movie`. Normalization (TMDB response → domain model) happens in `:backend`, not in `:app`.

### Credential management

- **Local dev:** Key read from environment variable or `local.properties` via the `:backend` build config — not `:app`.
- **Production:** Cloud Run + Google Secret Manager. Key injected at runtime as an environment variable.

### Commit boundary

One commit: working Ktor service with the three endpoints, deployable to Cloud Run.

---

## 2b. TMDB Data Layer

**Goal:** `:app` Repository can fetch fully-populated `Move` objects by calling `:backend`.

### Changes needed

1. Replace direct TMDB Retrofit client in `:app` with a Ktor Client pointed at `:backend`.
   Remove Retrofit and Gson dependencies. Use kotlinx.serialization for response parsing.
   (See Decision 006: prepares the data layer for Phase 5 KMP migration.)
2. Add `Repository.fetchMovieMove(movieId: Int): Move.Movie`
   - Calls `GET /movies/{id}/credits` on `:backend`.
   - Response maps directly to `Move.Movie` (castIds already normalized by backend).
3. Update search to return typed result objects with IDs (currently maps to `List<String>`, losing the ID).
   `searchMovies` returns `List<MovieSearchResult>`, `searchActors` returns `List<PersonSearchResult>`.
   `Move.Actor` is constructed directly in the ViewModel from the search result — no repository call needed.

### Design decision: validation direction

Both validation checks are handled by `GameEngine` using the `castIds` in `Move.Movie`. The `:app` layer fetches these from `:backend` and populates the move before calling `playMove`.
- If it's an **Actor's turn**, they pick a **Movie**. The `Move.Movie` must include the cast list (fetched from `:backend`).
- If it's a **Movie's turn**, they pick an **Actor**. The engine uses `castIds` from the *previous* `Move.Movie` in the chain — no additional network call needed.

### Commit boundary

One commit: updated domain models, repository methods that call `:backend` and return fully-populated `Move` objects.

---

## 3. Game Flow UI

**Goal:** Three screens. Player can navigate through a complete game.

### Screens

**Start Screen**
- Two text fields for player names (Optional for MVP, can default to "Player 1/2")
- "Start Game" button
- Navigates to actor search for Player 1 to pick starting actor

**Play Screen** (most complex)
- Header: current player name, prompt ("Name a movie **Tom Hanks** was in")
- Chain display: scrollable list of entries so far
- Search field + results list
- Selecting a result submits the move
- "I can't answer" forfeit button

**Game Over Screen**
- Winner announcement
- Full chain display
- "Play Again" button (returns to start screen)

### Navigation

```
StartScreen -> PlayScreen (starting actor selected)
PlayScreen -> GameOverScreen (game ends)
GameOverScreen -> StartScreen (play again)
```

Use Compose Navigation with a sealed route type. Game state lives in a ViewModel scoped to the nav graph.

### State management

```kotlin
class GameViewModel : ViewModel() {
    private val _uiState = MutableStateFlow<GameUiState>(GameUiState.Setup)
    val uiState: StateFlow<GameUiState> = _uiState.asStateFlow()
}

sealed class GameUiState {
    object Setup : GameUiState()
    data class Playing(
        val gameState: GameState,
        val searchResults: List<Move>,
        val searchQuery: String,
        val isSubmitting: Boolean
    ) : GameUiState()
    data class GameOver(val finalState: GameState.GameOver) : GameUiState()
}
```

The ViewModel owns the `GameState`, calls `GameEngine` for transitions, calls `Repository` for TMDB validation and search.

---

## 4. Integration

**Goal:** Wire TMDB validation into the game loop. A move submission triggers: search -> select -> fetch credits -> engine transition -> UI update.

### Flow

```
Player selects search result
  -> ViewModel calls Repository.fetch[Movie/Actor]Move(id)
  -> Repository hits TMDB credits API (if movie)
  -> ViewModel calls GameEngine.playMove(move, state)
  -> GameResult is InProgress or GameOver
  -> ViewModel updates UiState
  -> UI recomposes
```

### Commit boundary

One commit: wiring the pieces together. After this commit, the game is playable end-to-end.

---

## Build Order Summary

| Step | What | Depends on | Testable in isolation |
|------|------|------------|----------------------|
| 1 | Game engine | Nothing | **Done** |
| 2a | Backend proxy service | Nothing | Yes (against real TMDB) |
| 2b | TMDB data layer in `:app` | 2a | Yes (with fake backend) |
| 3 | Game flow UI | Engine types (for state) | Yes (with fake data) |
| 4 | Integration | 1 + 2a + 2b + 3 | Manual play-test |
