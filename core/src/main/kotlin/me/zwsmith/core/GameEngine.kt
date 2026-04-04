package me.zwsmith.core

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
  data class Movie(override val id: Int, override val displayText: String, val castIds: Set<Int>) :
    Move()
}

enum class Player {
  ONE,
  TWO;

  fun other(): Player {
    return when (this) {
      ONE -> TWO
      TWO -> ONE
    }
  }
}

interface GameEngine {
  fun startGame(move: Move): GameState.InProgress
  fun playMove(move: Move, state: GameState.InProgress): GameState
  fun forfeit(state: GameState.InProgress): GameState.GameOver
}

fun GameEngine(): GameEngine = DefaultGameEngine

object DefaultGameEngine : GameEngine {
  override fun startGame(move: Move): GameState.InProgress {
    return GameState.InProgress(
      moves = listOf(move),
      currentPlayer = Player.TWO
    )
  }

  override fun playMove(move: Move, state: GameState.InProgress): GameState {
    return if (isRepeat(move, state.moves) || !isValidConnection(move, state.moves.last())) {
      GameState.GameOver(
        winner = state.currentPlayer.other(),
        loser = state.currentPlayer,
        chain = state.moves,
        losingMove = move
      )
    } else {
      GameState.InProgress(
        moves = state.moves + move,
        currentPlayer = state.currentPlayer.other()
      )
    }
  }

  override fun forfeit(state: GameState.InProgress): GameState.GameOver {
    return GameState.GameOver(
      winner = state.currentPlayer.other(),
      loser = state.currentPlayer,
      chain = state.moves,
      losingMove = null
    )
  }

  private fun isRepeat(move: Move, moves: List<Move>): Boolean = when (move) {
    is Move.Actor -> moves.filterIsInstance<Move.Actor>().any { it.id == move.id }
    is Move.Movie -> moves.filterIsInstance<Move.Movie>().any { it.id == move.id }
  }

  private fun isValidConnection(move: Move, previousMove: Move): Boolean = when (previousMove) {
    is Move.Actor if move is Move.Movie -> move.castIds.contains(previousMove.id)
    is Move.Movie if move is Move.Actor -> previousMove.castIds.contains(move.id)
    else -> false // same type twice — shouldn't happen if UI enforces turn order
  }
}
