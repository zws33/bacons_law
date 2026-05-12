package me.zwsmith.baconslaw.ui.screens

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.filterIsInstance
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import me.zwsmith.baconslaw.BaconsLawApplication
import me.zwsmith.baconslaw.data.GameSession
import me.zwsmith.baconslaw.data.GameSessionRepository
import me.zwsmith.baconslaw.domain.PlayerInfo
import java.util.UUID

class StartScreenViewModel(
  private val gameSessionRepository: GameSessionRepository,
) : ViewModel() {

  private val _uiState = gameSessionRepository.session
    .filterIsInstance<GameSession.Lobby>()
    .map { UiState(players = it.players) }
    .stateIn(
      scope = viewModelScope,
      started = SharingStarted.WhileSubscribed(5_000),
      initialValue = UiState(emptyList())
    )
  val uiState: StateFlow<UiState> = _uiState

  val onStartEvent = gameSessionRepository.session

  init {
    gameSessionRepository.reset()
  }

  fun onAddPlayer(name: String) {
    val playerInfo = PlayerInfo(
      id = UUID.randomUUID().toString(),
      displayName = name
    )
    gameSessionRepository.addPlayer(playerInfo)
  }

  fun onRemovePlayer(id: String) {
    gameSessionRepository.removePlayer(id)
  }

  fun onStart() {
    gameSessionRepository.startGame()
  }

  companion object {
    val Factory = viewModelFactory {
      initializer {
        val app = checkNotNull(this[APPLICATION_KEY]) as BaconsLawApplication
        StartScreenViewModel(app.gameSessionRepository)
      }
    }
  }

  data class UiState(
    val players: List<PlayerInfo>
  )
}
