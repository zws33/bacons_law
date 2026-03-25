# Phase 1 Implementation Plan

Build order and design decisions for the playable MVP. Reference [GAME_SPEC.md](GAME_SPEC.md) for rules and behavior.

## Status

| Step | Status |
|------|--------|
| Build toolchain | **Done** |
| 1. Game engine rewrite | **Next** |
| 2. TMDB data layer | Pending |
| 3. Game flow UI | Pending |
| 4. Integration | Pending |

## Completed

### Build toolchain ✓

- Gradle 9.4.1, AGP 9.1, Kotlin 2.3.20, Compose BOM 2026.03.00
- `:core` converted to pure Kotlin JVM module (no Android deps)
- All AGP 9 defaults adopted — removed all compatibility shims
- Dependency bundles organized in version catalog
- `.idea/` gitignored, machine-specific config in `local.properties`

---

---

## 1. Game Engine Rewrite ← next

**Goal:** Pure Kotlin state machine that models the full game spec. No Android dependencies. Fully testable.

### Why rewrite (not adapt)

The existing engine has the right shape (sealed moves, turn list, player alternation) but:
- Winner logic is inverted (returns the losing player)
- No repeat detection
- No forfeit
- Validation is caller-side (credits embedded in the Move object)
- Mutable `var gameState` on a class — awkward for reactive UI

The engine is ~125 lines. Rewriting with the spec as the guide is faster and cleaner than patching.

### Design

**Immutable state, pure functions.** The engine is a function: `(GameState, Action) -> GameResult`. No mutable class, no side effects. The ViewModel holds the state; the engine computes transitions.

#### Types

```kotlin
data class GameState(
    val chain: List<ChainEntry>,
    val currentPlayer: Player,
    val players: Pair<PlayerInfo, PlayerInfo>,
    val nextMoveType: MoveType
)

data class PlayerInfo(val name: String)

enum class Player { ONE, TWO }
enum class MoveType { ACTOR, MOVIE }

sealed class ChainEntry {
    abstract val id: Int
    abstract val name: String
    data class Actor(override val id: Int, override val name: String) : ChainEntry()
    data class Movie(override val id: Int, override val name: String) : ChainEntry()
}

sealed class GameResult {
    data class Continue(val state: GameState) : GameResult()
    data class GameOver(
        val winner: Player,
        val loser: Player,
        val reason: EndReason,
        val chain: List<ChainEntry>
    ) : GameResult()
}

enum class EndReason { INVALID_CONNECTION, REPEAT, FORFEIT }
```

#### Engine API

```kotlin
object GameEngine {
    fun startGame(players: Pair<PlayerInfo, PlayerInfo>, startingActor: ChainEntry.Actor): GameState

    fun playMove(state: GameState, entry: ChainEntry, isValidConnection: Boolean): GameResult

    fun forfeit(state: GameState): GameResult
}
```

**Key decision: `isValidConnection` is a parameter, not computed by the engine.** The engine doesn't know about TMDB. The caller (ViewModel) checks the connection via TMDB, then tells the engine whether it's valid. This keeps the engine pure and testable without network mocks. The engine still checks for repeats independently.

### Test cases (derived from game spec)

- Starting a game sets Player 1's actor as first chain entry, next move is MOVIE, current player is TWO
- Valid non-repeat move advances the chain and switches player
- Invalid connection ends the game, current player loses
- Repeat actor in chain ends the game, current player loses
- Repeat movie in chain ends the game, current player loses
- Forfeit ends the game, current player loses
- Move type alternates: after actor, must be movie; after movie, must be actor
- Chain accumulates correctly across multiple moves

### Commit boundary

One commit: engine types + `GameEngine` + tests. All tests green.

---

## 2. TMDB Data Layer

**Goal:** Repository can answer: "Was this actor in this movie?" Both directions.

### Current state

- `Api.searchMovies(query)` — works
- `Api.searchActor(query)` — works
- `Api.getCredits(movieId)` — returns cast for a movie (actor-in-movie direction)
- **Missing:** `person/{personId}/movie_credits` — returns movies for an actor (movie-has-actor direction)

### Changes needed

1. Add `getPersonCredits(personId: Int)` to `Api` interface — calls `person/{id}/movie_credits`
2. Add response model for person credits
3. Add `Repository.validateConnection(entry: ChainEntry, previousEntry: ChainEntry): Boolean`
   - If previous is Actor and current is Movie: fetch movie credits, check if actor ID is in cast
   - If previous is Movie and current is Actor: fetch movie credits, check if actor ID is in cast
   - Both directions can use the movie credits endpoint (check if actor is in movie's cast). The person credits endpoint is a fallback/alternative.
4. Update search results to return domain models with IDs (currently maps to `List<String>`, losing the ID)

### Design decision: validation direction

Both validation checks can use a single endpoint: `movie/{id}/credits`. Given the previous entry, we always know the movie ID:
- Previous = Actor, Current = Movie: fetch credits for the current movie, check if previous actor is in cast
- Previous = Movie, Current = Actor: fetch credits for the previous movie, check if current actor is in cast

This means we may not need the person credits endpoint at all for MVP. Simpler API surface.

### Commit boundary

One commit: new API endpoint (if needed), validation method, updated domain models. Tested via unit test with a mock/fake API if feasible, otherwise integration-tested during UI wiring.

---

## 3. Game Flow UI

**Goal:** Three screens. Player can navigate through a complete game.

### Screens

**Start Screen**
- Two text fields for player names
- "Start Game" button (disabled until both names entered)
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
    data class Setup(...) : GameUiState()
    data class Playing(
        val gameState: GameState,
        val searchResults: List<...>,
        val searchQuery: String,
        val isValidating: Boolean
    ) : GameUiState()
    data class GameOver(...) : GameUiState()
}
```

The ViewModel owns the `GameState`, calls `GameEngine` for transitions, calls `Repository` for TMDB validation and search.

### Commit plan

This is too large for one commit. Break into vertical slices:
1. Navigation skeleton + Start screen (functional, navigates forward)
2. Play screen layout + search (displays, searches, but doesn't validate yet)
3. Game over screen + play again navigation

---

## 4. Integration

**Goal:** Wire TMDB validation into the game loop. A move submission triggers: search -> select -> validate via TMDB -> engine transition -> UI update.

### Flow

```
Player selects search result
  -> ViewModel calls Repository.validateConnection(selected, previousChainEntry)
  -> Repository hits TMDB credits API
  -> Returns Boolean
  -> ViewModel calls GameEngine.playMove(state, entry, isValid)
  -> GameResult is Continue or GameOver
  -> ViewModel updates UiState
  -> UI recomposes
```

### Loading state

TMDB validation is a network call. Between selection and result, show a loading indicator and disable interaction. This prevents double-submission and gives feedback.

### Error handling (minimal for MVP)

- Network failure on validation: show a toast/snackbar, let the player retry. Don't end the game on a network error.
- Network failure on search: show empty results with an error message.
- No internet: the app doesn't work. That's acceptable for MVP.

### Commit boundary

One commit: wiring the pieces together. After this commit, the game is playable end-to-end.

---

## Open Design Questions

### 1. Should search results be pre-filtered to valid connections?

**Option A: Show all results, validate on selection.** Player searches "Cast Away", sees all movies named "Cast Away", picks one, app validates. Simpler to build. Player might select a wrong movie (different from what they meant) and lose.

**Option B: Pre-filter to valid connections.** When it's "name a movie Tom Hanks was in", only show movies Tom Hanks was actually in. Requires fetching the actor's filmography before/during search and cross-referencing. More API calls, more complex, but prevents accidental misselection.

**Recommendation: Option A for MVP.** Simpler, and the "risk of misselection" is actually part of the game's tension — you need to be sure about your answer. The search results show title and year, which is enough to disambiguate.

### 2. Should the existing `SearchViewModel` and `BaconsLawApp` composable be reused?

**No.** The existing UI is a freestanding search demo with no game flow. The new UI needs navigation, game state, turn management, and validation. Reusing would mean retrofitting game logic into a structure that wasn't designed for it. Start fresh, keep the TMDB API/Repository layer.

### 3. Chain entry display — name only or name + metadata?

For MVP, name + year (movies) and name + photo (actors) would be ideal but requires passing through more TMDB data. **Start with name only**, add metadata in Phase 2 polish.

---

## Build Order Summary

| Step | What | Depends on | Testable in isolation |
|------|------|------------|----------------------|
| 1 | Game engine | Nothing | Yes (pure unit tests) |
| 2 | TMDB data layer | Nothing | Partially (needs API key for integration) |
| 3 | Game flow UI | Engine types (for state) | Yes (with fake data) |
| 4 | Integration | 1 + 2 + 3 | Manual play-test |

Steps 1 and 2 can be done in parallel. Step 3 depends on engine types but not behavior. Step 4 is the final wiring.
