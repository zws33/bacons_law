# Phase 1 Implementation Plan

Build order and design decisions for the playable MVP. Reference [GAME_SPEC.md](GAME_SPEC.md) for rules and behavior.

## Status

| Step | Status |
|------|--------|
| Build toolchain | **Done** |
| 1. Game engine rewrite | **Done** |
| 2. TMDB data layer | **Next** |
| 3. Game flow UI | Pending |
| 4. Integration | Pending |

## Completed

### Build toolchain ✓

- Gradle 9.4.1, AGP 9.1, Kotlin 2.1.10, Compose BOM 2026.03.01
- `:core` converted to pure Kotlin JVM module (no Android deps)
- All AGP 9 defaults adopted — removed all compatibility shims
- Dependency bundles organized in version catalog
- `.idea/` gitignored, machine-specific config in `local.properties`

### Game Engine Rewrite ✓

- Pure Kotlin state machine in `:core`.
- Sealed `GameState` (`InProgress`, `GameOver`).
- Sealed `Move` (`Actor`, `Movie`).
- Factory function `GameEngine()` provides `DefaultGameEngine`.
- Full unit test coverage with JUnit 5 and Truth.

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

## 2. TMDB Data Layer ← next

**Goal:** Repository can answer: "Was this actor in this movie?" Both directions.

### Current state

- `Api.searchMovies(query)` — works
- `Api.searchActor(query)` — works
- `Api.getCredits(movieId)` — returns cast for a movie (actor-in-movie direction)
- **Missing:** Mapping raw API responses to the `Move` models used by the engine.

### Changes needed

1. Add `Repository.fetchMovieMove(movieId: Int): Move.Movie`
   - Calls `Api.getCredits(movieId)` to get the cast IDs.
   - Fetches movie details if needed for `displayText`.
2. Add `Repository.fetchActorMove(actorId: Int): Move.Actor`
3. Update search results to return domain models with IDs (currently maps to `List<String>`, losing the ID).

### Design decision: validation direction

Both validation checks are handled by the `GameEngine` using the `castIds` provided in the `Move.Movie` object.
- If it's an **Actor's turn**, they pick a **Movie**. The `Move.Movie` object must include the cast list.
- If it's a **Movie's turn**, they pick an **Actor**. The engine uses the `castIds` from the *previous* `Move.Movie` in the chain.

### Commit boundary

One commit: updated domain models, repository methods to fetch fully-populated `Move` objects.

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
| 2 | TMDB data layer | Nothing | Partially |
| 3 | Game flow UI | Engine types (for state) | Yes (with fake data) |
| 4 | Integration | 1 + 2 + 3 | Manual play-test |
