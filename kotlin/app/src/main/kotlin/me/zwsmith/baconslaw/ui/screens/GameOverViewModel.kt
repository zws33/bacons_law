package me.zwsmith.baconslaw.ui.screens

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import me.zwsmith.baconslaw.BaconsLawApplication
import me.zwsmith.baconslaw.data.GameSessionRepository

class GameOverViewModel(
  private val gameSessionRepository: GameSessionRepository,
) : ViewModel() {

  fun reset() {
    gameSessionRepository.reset()
  }

  companion object {
    val Factory = viewModelFactory {
      initializer {
        val app = checkNotNull(this[APPLICATION_KEY]) as BaconsLawApplication
        GameOverViewModel(app.gameSessionRepository)
      }
    }
  }
}
