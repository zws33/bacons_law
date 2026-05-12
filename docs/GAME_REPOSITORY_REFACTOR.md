# Game Repository Refactor — Implementation Plan

Extract game state management from `GameViewModel` into a dedicated `GameRepository`. Introduce `MovesRepository` as a domain-aligned abstraction over TMDB data. The ViewModel becomes a thin observer that maps repository state + search results into a single `GameScreenUiState` for the UI.

---

## Current problems

- `GameViewModel` owns `GameState`, calls `GameEngine`, fetches TMDB data, manages the search pipeline, and tracks player names — too many responsibilities.
- The `:core` refactor changed `Player` (no more `Player.ONE`/`Player.TWO`), `GameState.InProgress` (now `currentPlayerIndex: Int` + `players: List<Player>`), and `GameEngine.startGame` (now takes `List<Player>`). `GameScreen` and `GameViewModel` reference removed APIs — the app currently does not compile.
- `GameEngine` interface has no concrete implementation.
- The `onGameOver` callback in `GameScreen` is never passed from `BaconsLawApp` — navigation to `GameOver` is broken.

---

## Target architecture

```
MovesRepository       — domain-aligned data layer: search for move candidates, enrich to valid moves
GameRepository        — owns GameState, wraps GameEngine (pure state transitions, no network)
GameViewModel         — observes both repositories; maps to GameScreenUiState
GameScreen            — single collectAsStateWithLifecycle call; renders GameScreenUiState
```

### The two-phase move flow

Searching and committing a move are two distinct operations with different data needs:

1. **Search** — the user types a query; the repository returns `List<MoveCandidate>` (display data only; enough to render a result row and disambiguate between same-name entries)
2. **Enrich** — the user selects a candidate; the repository returns a complete `Move` ready for the game engine (for movies: cast IDs fetched from TMDB on first selection, then cached; for actors: constructed directly from candidate data)

The ViewModel calls `movesRepository.search(query, moveType)` to populate the list and `movesRepository.getMove(candidate)` on selection. It never calls TMDB directly.

---

## Step 1 — Add `GameEngineImpl` to `:core`

**File:** `core/src/main/kotlin/me/zwsmith/core/GameEngineImpl.kt` (new)

The `GameEngine` interface exists but has no concrete class. Add one that delegates to the existing extension functions:

```kotlin
class GameEngineImpl : GameEngine {
  override fun startGame(players: List<Player>): GameState.InProgress =
    GameState.InProgress(players = players)

  override fun playMove(move: Move, state: GameState.InProgress): GameState =
    state.playMove(move)

  override fun forfeit(state: GameState.InProgress): GameState.GameOver =
    state.forfeit()
}
```

No Android dependencies — `:core` stays pure Kotlin/JVM.

---

## Step 2 — Create `MoveCandidate`, `MoveType`, and `MovesRepository`

**Files:**
- `app/data/MoveCandidate.kt` (new)
- `app/data/MovesRepository.kt` (new)
- `app/data/Repository.kt` — `ApiClient` becomes an internal data source; the `Repository` interface and `RepositoryImpl` class are deleted

This step replaces the existing `Repository`/`RepositoryImpl` abstraction. `ApiClient` is retained as an internal HTTP client but is no longer exposed through a public interface.

### Domain types

```kotlin
enum class MoveType { ACTOR, MOVIE }

sealed class MoveCandidate {
  abstract val id: Int
  abstract val displayText: String

  data class Actor(
    override val id: Int,
    override val displayText: String,
    val imageUrl: String?,
  ) : MoveCandidate()

  data class Movie(
    override val id: Int,
    override val displayText: String,
    val releaseYear: String?,
  ) : MoveCandidate()
}
```

Design notes:
- `MoveCandidate` is a sealed class — subtypes carry only what's needed to render a result row and disambiguate same-name entries. Actors get a profile image URL; movies get a release year. Neither carries cast IDs — those come from the enrichment step.
- Movie images are intentionally excluded: poster art often reveals cast members, which spoils subsequent turns. Release year is sufficient for disambiguation in practice.
- The chain display (played moves) renders only `Move.displayText` — qualifier data is for selection UI only.

### Repository interface

```kotlin
interface MovesRepository {
  suspend fun search(query: String, moveType: MoveType): List<MoveCandidate>
  suspend fun getMove(candidate: MoveCandidate): Move
}
```

The interface speaks in domain terms. Callers have no knowledge of TMDB.

### Implementation

```kotlin
class MovesRepositoryImpl(
  private val apiClient: ApiClient,
) : MovesRepository {

  private val movieCache = mutableMapOf<Int, Move.Movie>()

  override suspend fun search(query: String, moveType: MoveType): List<MoveCandidate> {
    return when (moveType) {
      MoveType.ACTOR -> apiClient.searchActors(query).map { person ->
        MoveCandidate.Actor(
          id = person.id,
          displayText = person.name,
          imageUrl = person.profilePath?.let { TMDB_IMAGE_BASE_URL + it },
        )
      }
      MoveType.MOVIE -> apiClient.searchMovies(query).map { movie ->
        MoveCandidate.Movie(
          id = movie.id,
          displayText = movie.title,
          releaseYear = movie.releaseYear,
        )
      }
    }
  }

  override suspend fun getMove(candidate: MoveCandidate): Move {
    return when (candidate) {
      is MoveCandidate.Actor -> Move.Actor(
        id = candidate.id,
        displayText = candidate.displayText,
        imagePath = candidate.imageUrl,
      )
      is MoveCandidate.Movie -> {
        movieCache.getOrPut(candidate.id) {
          val credits = apiClient.fetchCredits(candidate.id)
          Move.Movie(
            id = candidate.id,
            displayText = candidate.displayText,
            castIds = credits.castIds,
            imagePath = null,
            releaseYear = candidate.releaseYear,
          )
        }
      }
    }
  }

  companion object {
    private const val TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w185"
    fun create(): MovesRepository = MovesRepositoryImpl(ApiClient.create())
  }
}
```

Cache notes:
- `movieCache` is an in-memory `Map<Int, Move.Movie>`. The first time a movie is selected, cast IDs are fetched and the complete `Move.Movie` is stored. Subsequent selections of the same movie return immediately from cache with no network call.
- The cache is scoped to the `MovesRepositoryImpl` instance. For the current architecture (single ViewModel, process lifetime), this is sufficient.
- Upgrading to a Room-backed persistent cache is a self-contained change inside this class — the `MovesRepository` interface and all callers are unaffected.

---

## Step 3 — Create `GameSession` and `GameRepository`

**File:** `app/data/GameRepository.kt` (new)

`GameState` has no concept of player names — `:core` must stay platform-free. Names live in a wrapper alongside the state:

```kotlin
data class GameSession(
  val state: GameState,
  val playerNames: Map<Player, String>,
)

interface GameRepository {
  val session: StateFlow<GameSession?>
  fun startGame(playerOneName: String, playerTwoName: String)
  fun playMove(move: Move)
  fun forfeit()
  fun resetGame()
}

class GameRepositoryImpl(private val engine: GameEngine) : GameRepository {
  private val _session = MutableStateFlow<GameSession?>(null)
  override val session: StateFlow<GameSession?> = _session

  override fun startGame(playerOneName: String, playerTwoName: String) {
    val players = listOf(Player(1), Player(2))
    _session.value = GameSession(
      state = engine.startGame(players),
      playerNames = mapOf(players[0] to playerOneName, players[1] to playerTwoName),
    )
  }

  override fun playMove(move: Move) {
    val s = _session.value ?: return
    val inProgress = s.state as? GameState.InProgress ?: return
    _session.value = s.copy(state = engine.playMove(move, inProgress))
  }

  override fun forfeit() {
    val s = _session.value ?: return
    val inProgress = s.state as? GameState.InProgress ?: return
    _session.value = s.copy(state = engine.forfeit(inProgress))
  }

  override fun resetGame() {
    _session.value = null
  }
}
```

Design notes:
- `session: StateFlow<GameSession?>` — null means no game active. Avoids adding a `NotStarted` sealed subtype to `:core`.
- `GameRepository` has no dependency on `MovesRepository`. State transitions are synchronous and pure — they never require network access.

---

## Step 4 — Rewrite `GameViewModel`

**File:** `app/ui/GameViewModel.kt`

### New state types

`SearchResultItem` is deleted. Search results are now `List<MoveCandidate>` — the repository owns all mapping from TMDB DTOs to domain types.

```kotlin
sealed interface GameScreenUiState {
  data object NotStarted : GameScreenUiState
  data class InProgress(
    val currentPlayerName: String,
    val moves: List<Move>,
    val searchState: SearchState,
    val isSubmitting: Boolean,
  ) : GameScreenUiState
  data class GameOver(val winnerName: String, val chain: List<Move>) : GameScreenUiState
}

sealed interface SearchState {
  data object Idle : SearchState
  data object Loading : SearchState
  data class Results(val items: List<MoveCandidate>) : SearchState
  data class Error(val message: String) : SearchState
}
```

### Deriving `MoveType` from game state

The ViewModel needs to know which type to search based on the last played move:

```kotlin
private fun GameState.InProgress.nextMoveType(): MoveType =
  if (moves.isEmpty() || moves.last() is Move.Movie) MoveType.ACTOR else MoveType.MOVIE
```

### ViewModel structure

```kotlin
class GameViewModel(
  private val gameRepository: GameRepository,
  private val movesRepository: MovesRepository,
) : ViewModel() {

  private val _searchQuery = MutableStateFlow("")
  var query by mutableStateOf("")
    private set
  private val _isSubmitting = MutableStateFlow(false)

  private val searchState: StateFlow<SearchState> = _searchQuery
    .debounce(300L)
    .distinctUntilChanged()
    .flatMapLatest { query ->
      if (query.isBlank()) return@flatMapLatest flowOf(SearchState.Idle)
      flow {
        emit(SearchState.Loading)
        val inProgress = (gameRepository.session.value?.state as? GameState.InProgress)
          ?: run { emit(SearchState.Idle); return@flow }
        val results = movesRepository.search(query, inProgress.nextMoveType())
        emit(SearchState.Results(results))
      }.catch { e ->
        Timber.e(e)
        emit(SearchState.Error("Couldn't load results. Check your connection."))
      }
    }
    .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), SearchState.Idle)

  val screenUiState: StateFlow<GameScreenUiState> = combine(
    gameRepository.session,
    searchState,
    _isSubmitting,
  ) { session, searchState, isSubmitting ->
    when {
      session == null -> GameScreenUiState.NotStarted
      session.state is GameState.GameOver -> GameScreenUiState.GameOver(
        winnerName = session.playerNames[session.state.winner] ?: "Player",
        chain = session.state.chain,
      )
      session.state is GameState.InProgress -> {
        val current = session.state.players[session.state.currentPlayerIndex]
        GameScreenUiState.InProgress(
          currentPlayerName = session.playerNames[current] ?: "Player",
          moves = session.state.moves,
          searchState = searchState,
          isSubmitting = isSubmitting,
        )
      }
      else -> GameScreenUiState.NotStarted
    }
  }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), GameScreenUiState.NotStarted)

  fun startGame(playerOne: String, playerTwo: String) {
    gameRepository.startGame(playerOne, playerTwo)
    reset()
  }

  fun forfeit() {
    gameRepository.forfeit()
    reset()
  }

  fun resetGame() {
    gameRepository.resetGame()
    reset()
  }

  fun reset() {
    query = ""
    _searchQuery.value = ""
  }

  fun onTextInput(value: String) {
    query = value
    _searchQuery.value = value
  }

  fun onResultSelected(candidate: MoveCandidate) {
    if (_isSubmitting.value) return
    viewModelScope.launch {
      _isSubmitting.value = true
      try {
        val move = movesRepository.getMove(candidate)
        gameRepository.playMove(move)
        reset()
      } catch (e: Exception) {
        Timber.e(e)
      } finally {
        _isSubmitting.value = false
      }
    }
  }

  companion object {
    val Factory = viewModelFactory {
      initializer {
        GameViewModel(
          gameRepository = GameRepositoryImpl(GameEngineImpl()),
          movesRepository = MovesRepositoryImpl.create(),
        )
      }
    }
  }
}
```

Note how `onResultSelected` compares to the previous version: the move type branching and credits fetching logic are gone. The ViewModel calls `getMove` — the repository handles enrichment, caching, and `Move` construction. The ViewModel has no knowledge of TMDB.

---

## Step 5 — Update `GameScreen`

**File:** `app/ui/screens/GameScreen.kt`

Replace the three separate `collectAsStateWithLifecycle` calls with one:

```kotlin
val screenUiState by viewModel.screenUiState.collectAsStateWithLifecycle()
```

Top-level `when`:

```kotlin
when (val state = screenUiState) {
  is GameScreenUiState.NotStarted -> { /* nav invariant — should not render here */ }

  is GameScreenUiState.GameOver -> {
    // LaunchedEffect, not a direct call — side effects must not run during composition
    LaunchedEffect(state.winnerName) { onGameOver(state.winnerName) }
  }

  is GameScreenUiState.InProgress -> {
    // use state.currentPlayerName, state.moves, state.isSubmitting
    // inner when on state.searchState:
    when (val search = state.searchState) {
      is SearchState.Idle ->
        if (state.isSubmitting) CircularProgressIndicator else ChainDisplay(state.moves)
      is SearchState.Loading -> CircularProgressIndicator
      is SearchState.Results ->
        if (search.items.isEmpty() && viewModel.query.isNotBlank()) NoResultsText
        else ResultsList(search.items, viewModel::onResultSelected)
      is SearchState.Error ->
        ErrorMessage(search.message, onDismiss = viewModel::reset)
    }
  }
}
```

`ResultsList` now accepts `List<MoveCandidate>` instead of `List<SearchResultItem>`. Update its signature and rendering logic accordingly:
- `MoveCandidate.Actor` → render `imageUrl` as a profile photo
- `MoveCandidate.Movie` → render `releaseYear` as a subtitle; no image
- Chain display (`ChainDisplay` / `ChainItem`) renders `Move.displayText` only — no images for movies, no release year qualifier needed

Note on `LaunchedEffect` vs direct call: the current code calls `onGameOver()` directly during composition, which is incorrect. `LaunchedEffect(state.winnerName)` fires once after the composition succeeds and won't re-fire unless `winnerName` changes.

---

## Step 6 — Fix `BaconsLawApp.kt` wiring

**File:** `app/ui/BaconsLawApp.kt`

**1. Remove the `playerNames` observer** — it no longer exists on `GameViewModel`:

```kotlin
// delete this line
val playerNames by viewModel.playerNames.collectAsStateWithLifecycle()
```

**2. Wire `onGameOver` and fix Play Again navigation:**

```kotlin
composable<InProgress> {
  GameScreen(
    modifier = contentModifier,
    viewModel = viewModel,
    onGameOver = { winner -> navController.navigate(GameOver(winner = winner)) },
  )
}
composable<GameOver> { backStackEntry ->
  val gameOver = backStackEntry.toRoute<GameOver>()
  GameOverScreen(
    state = gameOver,
    onPlayAgain = {
      viewModel.resetGame()
      navController.popBackStack(GameStart, inclusive = false)
    },
  )
}
```

`popBackStack(GameStart, inclusive = false)` pops back to `GameStart` without destroying it, clearing `InProgress` and `GameOver` from the back stack cleanly.

---

## Checklist

| # | Step | File(s) | Status |
|---|------|---------|--------|
| 1 | Add `GameEngineImpl` | `core/.../GameEngineImpl.kt` | [ ] |
| 2 | Create `MoveCandidate`, `MoveType`, `MovesRepository` | `app/data/MoveCandidate.kt`, `app/data/MovesRepository.kt`, `app/data/Repository.kt` (delete old interface) | [ ] |
| 3 | Add `GameSession` + `GameRepository` | `app/data/GameRepository.kt` | [ ] |
| 4 | Rewrite `GameViewModel` | `app/ui/GameViewModel.kt` | [ ] |
| 5 | Update `GameScreen` + `ResultsList` | `app/ui/screens/GameScreen.kt`, `app/ui/components/SharedComponents.kt` | [ ] |
| 6 | Fix `BaconsLawApp` wiring | `app/ui/BaconsLawApp.kt` | [ ] |

Each step leaves the codebase in a compilable state. Start with Step 1 — nothing downstream can compile until `GameEngineImpl` exists.
