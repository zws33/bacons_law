@file:OptIn(ExperimentalCoroutinesApi::class)

package me.zwsmith.baconslaw.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import me.zwsmith.baconslaw.data.Repository
import me.zwsmith.core.GameEngine
import me.zwsmith.core.GameState
import me.zwsmith.core.Move
import me.zwsmith.core.Player
import timber.log.Timber

sealed interface GameUiState {
  object Idle : GameUiState
  object Loading : GameUiState
  data class Success(val results: List<SearchResultItem>) : GameUiState
  data class Error(val message: String) : GameUiState
}

@OptIn(FlowPreview::class)
class GameViewModel(private val repository: Repository, private val gameEngine: GameEngine) :
  ViewModel() {

  private val _playerNames = MutableStateFlow<Pair<String, String>?>(null)
  val playerNames: StateFlow<Pair<String, String>?> = _playerNames

  private val _gameState =
    MutableStateFlow<GameState>(GameState.InProgress(emptyList(), Player.ONE))
  val gameState: StateFlow<GameState> = _gameState

  private val _searchQuery = MutableStateFlow("")

  var query by mutableStateOf("")
    private set

  private val _isSubmitting = MutableStateFlow(false)
  val isSubmitting: StateFlow<Boolean> = _isSubmitting

  val uiState: StateFlow<GameUiState> = _searchQuery
    .debounce(300L)
    .distinctUntilChanged()
    .flatMapLatest { query ->
      if (query.isBlank()) {
        flowOf(GameUiState.Idle)
      } else {
        flow {
          emit(GameUiState.Loading)
          val gameState = _gameState.value
          if (gameState is GameState.InProgress) {
            val results = if (gameState.moves.isEmpty() || gameState.moves.last() is Move.Movie) {
              repository.searchActors(query).map { SearchResultItem(it.id, it.name, it.profilePath) }
            } else {
              repository.searchMovies(query).map {
                SearchResultItem(it.id, it.title, it.posterPath, it.releaseYear)
              }
            }
            emit(GameUiState.Success(results))
          } else {
            emit(GameUiState.Idle)
          }
        }.catch { e ->
          Timber.e(e)
          emit(GameUiState.Error("Couldn't load results. Check your connection."))
        }
      }
    }
    .stateIn(
      scope = viewModelScope,
      started = SharingStarted.WhileSubscribed(5_000),
      initialValue = GameUiState.Idle
    )

  fun reset() {
    query = ""
    _searchQuery.value = ""
  }

  fun startGame(playerOne: String, playerTwo: String) {
    _playerNames.value = Pair(playerOne, playerTwo)
    _gameState.value = GameState.InProgress(emptyList(), Player.ONE)
    reset()
  }

  fun forfeit() {
    val state = _gameState.value as? GameState.InProgress ?: return
    _gameState.value = gameEngine.forfeit(state)
    reset()
  }

  fun resetGame() {
    _playerNames.value = null
    _gameState.value = GameState.InProgress(emptyList(), Player.ONE)
    reset()
  }

  fun onTextInput(query: String) {
    this.query = query
    _searchQuery.value = query
  }

  fun onResultSelected(item: SearchResultItem) {
    val gameState = _gameState.value as? GameState.InProgress ?: return
    if (_isSubmitting.value) return

    viewModelScope.launch {
      _isSubmitting.value = true
      try {
        when (val previous = gameState.moves.lastOrNull()) {
          is Move.Actor -> {
            val creditsResult = repository.fetchMovieCredits(item.id)
            _gameState.value = gameEngine.playMove(
              Move.Movie(
                item.id,
                item.displayText,
                creditsResult.castIds.toSet(),
                item.imagePath,
                item.releaseYear
              ), gameState
            )
          }

          is Move.Movie -> {
            _gameState.value =
              gameEngine.playMove(Move.Actor(item.id, item.displayText, item.imagePath), gameState)
          }

          null -> {
            _gameState.value =
              gameEngine.startGame(Move.Actor(item.id, item.displayText, item.imagePath))
          }
        }
        reset()
      } catch (e: Exception) {
        Timber.e(e)
        // Note: For a real app, we'd add a _submissionError flow here.
      } finally {
        _isSubmitting.value = false
      }
    }
  }

  companion object {
    val Factory = viewModelFactory {
      initializer {
        val repository = Repository()
        val gameEngine = GameEngine()
        GameViewModel(repository, gameEngine)
      }
    }
  }
}

data class SearchResultItem(
  val id: Int,
  val displayText: String,
  val imagePath: String? = null,
  val releaseYear: String? = null
)
