package me.zwsmith.core

fun GameEngine(): GameEngine = GameEngineImpl()

interface GameEngine {
  fun playMove(currentState: GameState.InProgress, move: Move): GameState
  fun forfeit(currentState: GameState.InProgress): GameState.GameOver
}

class GameEngineImpl : GameEngine {
  override fun playMove(currentState: GameState.InProgress, move: Move): GameState {
    return currentState.playMove(move)
  }

  override fun forfeit(currentState: GameState.InProgress): GameState.GameOver {
    return currentState.forfeit()
  }
}

sealed class GameState {
  data class InProgress(
    val moves: List<Move> = emptyList(),
    val currentPlayerIndex: Int = 0,
    val playerCount: Int,
  ) : GameState()

  data class GameOver(
    val winnerIndex: Int,
    val chain: List<Move>,
    val losingMove: Move? = null,
  ) : GameState()
}

sealed class Move {
  abstract val id: Int
  abstract val displayText: String
  abstract val imagePath: String?

  data class Actor(
    override val id: Int,
    override val displayText: String,
    override val imagePath: String? = null
  ) : Move()

  data class Movie(
    override val id: Int,
    override val displayText: String,
    val castIds: Set<Int>,
    override val imagePath: String? = null,
    val releaseYear: String? = null
  ) : Move()
}

fun GameState.InProgress.playMove(move: Move): GameState {
  return if (moves.isNotEmpty() && (isRepeat(move, moves) || !isValidConnection(move, moves.last()))) {
    GameState.GameOver(
      winnerIndex = previous(currentPlayerIndex, playerCount),
      chain = moves,
      losingMove = move,
    )
  } else {
    copy(
      moves = moves + move,
      currentPlayerIndex = next(currentPlayerIndex, playerCount),
    )
  }
}

fun GameState.InProgress.forfeit(): GameState.GameOver {
  return GameState.GameOver(
    winnerIndex = previous(currentPlayerIndex, playerCount),
    chain = moves,
    losingMove = null,
  )
}

private fun isRepeat(move: Move, moves: List<Move>): Boolean = when (move) {
  is Move.Actor -> moves.filterIsInstance<Move.Actor>().any { it.id == move.id }
  is Move.Movie -> moves.filterIsInstance<Move.Movie>().any { it.id == move.id }
}

private fun isValidConnection(move: Move, previousMove: Move): Boolean = when (previousMove) {
  is Move.Actor if move is Move.Movie -> move.castIds.contains(previousMove.id)
  is Move.Movie if move is Move.Actor -> previousMove.castIds.contains(move.id)
  else -> false
}

private fun next(current: Int, count: Int) = (current + 1) % count

private fun previous(current: Int, count: Int) = (current - 1 + count) % count
