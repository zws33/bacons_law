package com.zwsmith.bacons_law.presentation

class Game {

    var gameState: GameState = IntialState
        private set

    fun playMove(move: GameMove) {
        if (gameState.progress == Progress.NOT_STARTED) {
            gameState = gameState.copy(progress = Progress.IN_PROGRESS)
        }
        val lastMove = gameState.turns.lastOrNull()?.move
        when (move) {
            is GameMove.Actor -> {
                playActor(lastMove, move)
            }
            is GameMove.Movie -> {
                playMovie(lastMove, move)
            }
        }
    }

    private fun playActor(
        lastMove: GameMove?,
        move: GameMove.Actor
    ) {
        gameState = when (lastMove) {
            is GameMove.Actor -> throw IllegalStateException("Expected last move to be Movie")
            is GameMove.Movie -> {
                if (lastMove.actors.contains(move.id)) {
                    advanceGame(move)
                } else {
                    gameState.copy(progress = Progress.COMPLETE)
                }
            }
            null -> {
                gameState.copy(
                    turns = gameState.turns.plus(Turn(move, gameState.currentPlayer))
                )
            }
        }
    }

    private fun getNextPlayer() = when (gameState.currentPlayer) {
        Player.ONE -> Player.TWO
        Player.TWO -> Player.ONE
    }

    private fun playMovie(
        lastMove: GameMove?,
        move: GameMove
    ) {
        gameState = when (lastMove) {
            is GameMove.Movie -> throw IllegalStateException("Expected last move to be Actor")
            is GameMove.Actor -> {
                if (lastMove.movies.contains(move.id)) {
                    advanceGame(move)
                } else {
                    gameState.copy(progress = Progress.COMPLETE)
                }
            }
            null -> {
                advanceGame(move)
            }
        }
    }

    private fun advanceGame(move: GameMove): GameState {
        val newMoves = gameState.turns.plus(Turn(move, gameState.currentPlayer))
        return gameState.copy(turns = newMoves, currentPlayer = getNextPlayer())
    }

    fun getWinner(): Player? {
        return if (gameState.progress == Progress.COMPLETE) {
            gameState.turns.lastOrNull()?.player
        } else {
            null
        }
    }


    data class GameState(
        val progress: Progress,
        val turns: List<Turn>,
        val currentPlayer: Player
    )

    enum class Progress {
        COMPLETE,
        IN_PROGRESS,
        NOT_STARTED
    }

    enum class Player {
        ONE,
        TWO
    }

    data class Turn(
        val move: GameMove,
        val player: Player
    )

    sealed class GameMove {
        abstract val id: Int

        data class Movie(
            override val id: Int,
            val actors: List<Int>
        ) : GameMove()

        data class Actor(
            override val id: Int,
            val movies: List<Int>
        ) : GameMove()
    }

    companion object {
        val IntialState = GameState(
            progress = Progress.NOT_STARTED,
            turns = emptyList(),
            currentPlayer = Player.ONE
        )
    }
}