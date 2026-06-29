@file:OptIn(ExperimentalCoroutinesApi::class)

package me.zwsmith.baconslaw.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filterIsInstance
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import me.zwsmith.baconslaw.BaconsLawApplication
import me.zwsmith.baconslaw.data.GameSession
import me.zwsmith.baconslaw.data.GameSessionRepository
import me.zwsmith.baconslaw.data.MoveCandidate
import me.zwsmith.baconslaw.data.MoveType
import me.zwsmith.baconslaw.data.MovesRepository
import me.zwsmith.baconslaw.domain.PlayerInfo
import me.zwsmith.core.Move


data class UiState(
  val currentPlayerDisplayText: String,
  val movesChain: List<Move>,
  val searchState: SearchState,
)

sealed class SearchState {
  data class Idle(
    val results: List<MoveCandidate> = emptyList(),
  ) : SearchState()

  object Searching : SearchState()
  data class Error(val message: String) : SearchState()
}


@OptIn(FlowPreview::class)
class GameplayViewModel(
  private val movesRepository: MovesRepository,
  private val gameSessionRepository: GameSessionRepository,
) : ViewModel() {

  private val _searchQuery = MutableStateFlow("")
  private val _searchState = MutableStateFlow<SearchState>(SearchState.Idle())

  private val _gameOverEvent = MutableSharedFlow<String>(extraBufferCapacity = 1)
  val gameOverEvent: SharedFlow<String> = _gameOverEvent

  var query by mutableStateOf("")
    private set

  val uiState: StateFlow<UiState> = combine(
    gameSessionRepository.session.filterIsInstance<GameSession.InProgress>(),
    _searchState,
  ) { session, searchState ->
    UiState(
      currentPlayerDisplayText = session.currentPlayer.displayName,
      movesChain = session.gameState.moves,
      searchState = searchState,
    )
  }.stateIn(
    scope = viewModelScope,
    started = SharingStarted.WhileSubscribed(5_000),
    initialValue = UiState("", emptyList(), SearchState.Idle()),
  )

  init {
    viewModelScope.launch {
      gameSessionRepository.session.filterIsInstance<GameSession.GameOver>().collect { session ->
        _gameOverEvent.emit(session.winner.displayName)
      }
    }
    viewModelScope.launch {
      _searchQuery
        .debounce(300)
        .distinctUntilChanged()
        .flatMapLatest { q ->
          if (q.isBlank()) {
            flowOf<SearchState>(SearchState.Idle())
          } else {
            flow {
              emit(SearchState.Searching)
              val result = runCatching {
                val session = gameSessionRepository.session.value
                val moveType = if (session is GameSession.InProgress) {
                  when (session.gameState.moves.lastOrNull()) {
                    is Move.Actor -> MoveType.MOVIE
                    is Move.Movie -> MoveType.ACTOR
                    null -> MoveType.ACTOR
                  }
                } else MoveType.ACTOR
                movesRepository.search(q, moveType)
              }.fold(
                onSuccess = { SearchState.Idle(it) },
                onFailure = { SearchState.Error(it.message ?: "Search failed") },
              )
              emit(result)
            }
          }
        }
        .collect { _searchState.value = it }
    }
  }

  private fun reset() {
    query = ""
    _searchQuery.value = ""
    _searchState.value = SearchState.Idle()
  }

  fun onDismissError() {
    reset()
  }

  fun forfeit() {
    gameSessionRepository.forfeit()
    reset()
  }

  fun resetGame() {
    reset()
  }

  fun onTextInput(input: String) {
    query = input
    _searchQuery.value = input
  }

  fun onResultSelected(moveCandidate: MoveCandidate) {
    viewModelScope.launch {
      val move = movesRepository.getMove(moveCandidate)
      gameSessionRepository.playMove(move)
      reset()
    }
  }

  companion object {
    val Factory = viewModelFactory {
      initializer {
        val app = checkNotNull(this[APPLICATION_KEY]) as BaconsLawApplication
        GameplayViewModel(
          movesRepository = MovesRepository(),
          gameSessionRepository = app.gameSessionRepository,
        )
      }
    }
  }
}

private val GameSession.GameOver.winner: PlayerInfo
  get() = players[gameState.winnerIndex]

private val GameSession.InProgress.currentPlayer: PlayerInfo
  get() = players[gameState.currentPlayerIndex]
