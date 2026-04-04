package me.zwsmith.baconslaw.presentation

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import me.zwsmith.core.GameEngine
import me.zwsmith.core.GameState
import me.zwsmith.core.Move
import me.zwsmith.core.Player

class SearchViewModel(private val repository: Repository, private val gameEngine: GameEngine) :
  ViewModel() {

  private val _searchResults = MutableStateFlow<List<SearchResultItem>>(emptyList())
  val searchResults: StateFlow<List<SearchResultItem>> = _searchResults
  private val _gameState =
    MutableStateFlow<GameState>(GameState.InProgress(emptyList(), Player.ONE))

  val gameState: StateFlow<GameState> = _gameState

  var query by mutableStateOf("")
    private set

  fun reset() {
    query = ""
  }

  fun onTextInput(query: String) {
    this.query = query
    val gameState = _gameState.value
    if (gameState is GameState.InProgress) {
      viewModelScope.launch {
        _searchResults.value =
          if (gameState.moves.isEmpty() || gameState.moves.last() is Move.Movie) {
            repository.searchActors(query).map { SearchResultItem(it.id, it.name) }
          } else {
            repository.searchMovies(query).map { SearchResultItem(it.id, it.title) }
          }
      }
    }
  }

  fun onResultSelected(item: SearchResultItem) {
    val gameState = _gameState.value as? GameState.InProgress ?: return
    viewModelScope.launch {
      when (gameState.moves.lastOrNull()) {
        is Move.Actor -> {
          val creditsResult = repository.fetchMovieCredits(item.id)
          if (creditsResult != null) {
            _gameState.value = gameEngine.playMove(
              Move.Movie(item.id, item.displayText, creditsResult.castIds.toSet()), gameState
            )
          }
        }

        is Move.Movie -> {
          _gameState.value = gameEngine.playMove(Move.Actor(item.id, item.displayText), gameState)
        }

        null -> {
          _gameState.value = gameEngine.startGame(Move.Actor(item.id, item.displayText))
        }
      }
      reset()
      _searchResults.value = emptyList()
    }
  }

  companion object {
    private const val TAG = "SearchViewModel"
    val Factory = viewModelFactory {
      initializer {
        val repository = Repository()
        val gameEngine = GameEngine()
        SearchViewModel(repository, gameEngine)
      }
    }
  }
}

data class SearchResultItem(val id: Int, val displayText: String)
