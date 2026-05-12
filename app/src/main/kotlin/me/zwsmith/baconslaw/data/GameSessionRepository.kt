package me.zwsmith.baconslaw.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import me.zwsmith.baconslaw.domain.PlayerInfo
import me.zwsmith.core.GameEngine
import me.zwsmith.core.GameState
import me.zwsmith.core.Move

fun GameSessionRepository(): GameSessionRepository = GameSessionRepositoryImpl(GameEngine())

interface GameSessionRepository {
  val session: StateFlow<GameSession>
  fun playMove(move: Move)
  fun addPlayer(playerInfo: PlayerInfo)
  fun removePlayer(playerId: String)
  fun forfeit()
  fun reset()
  fun startGame()
}


sealed class GameSession {
  data class Lobby(
    val players: List<PlayerInfo> = emptyList()
  ) : GameSession()

  data class InProgress(
    val gameState: GameState.InProgress,
    val players: List<PlayerInfo>,
  ) : GameSession()

  data class GameOver(
    val gameState: GameState.GameOver,
    val players: List<PlayerInfo>,
  ) : GameSession()
}

class GameSessionRepositoryImpl(private val gameEngine: GameEngine) : GameSessionRepository {
  private val _session = MutableStateFlow<GameSession>(GameSession.Lobby())
  override val session: StateFlow<GameSession> = _session

  override fun addPlayer(playerInfo: PlayerInfo) {
    _session.update { current ->
      check(current is GameSession.Lobby) { "Add player called for non-lobby session: ${current::class.simpleName}" }
      current.copy(players = current.players + playerInfo)
    }
  }

  override fun removePlayer(playerId: String) {
    _session.update { current ->
      check(current is GameSession.Lobby) { "Remove player called for invalid session state: ${current::class.simpleName}" }
      current.copy(players = current.players.filter { it.id != playerId })
    }
  }

  override fun startGame() {
    _session.update { current ->
      check(current is GameSession.Lobby) { "Start game called for invalid session state: ${current::class.simpleName}" }
      GameSession.InProgress(
        players = current.players,
        gameState = GameState.InProgress(playerCount = current.players.size)
      )
    }
  }

  override fun playMove(move: Move) {
    _session.update { current ->
      check(current is GameSession.InProgress) { "Play move called for invalid session state: ${current::class.simpleName}" }
      when (val newState = gameEngine.playMove(current.gameState, move)) {
        is GameState.InProgress -> GameSession.InProgress(newState, current.players)
        is GameState.GameOver -> GameSession.GameOver(newState, current.players)
      }
    }
  }

  override fun forfeit() {
    _session.update { current ->
      check(current is GameSession.InProgress) { "Forfeit called for invalid session state: ${current::class.simpleName}" }
      val newState = gameEngine.forfeit(current.gameState)
      GameSession.GameOver(newState, current.players)
    }
  }

  override fun reset() {
    _session.update { GameSession.Lobby() }
  }
}
