package com.zwsmith.core

class Game {

    var gameState: GameState = IntialState
        private set

    fun playMove(move: Move) {
        if (gameState.progress == Progress.NOT_STARTED) {
            gameState = gameState.copy(progress = Progress.IN_PROGRESS)
        }
        val lastMove = gameState.turns.lastOrNull()?.move
        when (move) {
            is Move.Actor -> {
                playActor(lastMove, move)
            }
            is Move.Movie -> {
                playMovie(lastMove, move)
            }
        }
    }

    private fun playActor(
        lastMove: Move?,
        move: Move.Actor
    ) {
        gameState = when (lastMove) {
            is Move.Actor -> throw IllegalStateException("Expected last move to be Movie")
            is Move.Movie -> {
                if (lastMove.actors.contains(move.id)) {
                    advanceGame(move)
                } else {
                    finish()
                }
            }
            null -> {
                advanceGame(move)
            }
        }
    }

    private fun getNextPlayer() = when (gameState.currentPlayer) {
        Player.ONE -> Player.TWO
        Player.TWO -> Player.ONE
    }

    private fun playMovie(
        lastMove: Move?,
        move: Move
    ) {
        gameState = when (lastMove) {
            is Move.Movie -> throw IllegalStateException("Expected last move to be Actor")
            is Move.Actor -> {
                if (lastMove.movies.contains(move.id)) {
                    advanceGame(move)
                } else {
                    finish()
                }
            }
            null -> {
                advanceGame(move)
            }
        }
    }

    private fun finish() = gameState.copy(progress = Progress.COMPLETE)

    private fun advanceGame(move: Move): GameState {
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
        val move: Move,
        val player: Player
    )

    sealed class Move {
        abstract val id: Int

        data class Movie(
            override val id: Int,
            val actors: List<Int>
        ) : Move()

        data class Actor(
            override val id: Int,
            val movies: List<Int>
        ) : Move()
    }

    companion object {
        val IntialState = GameState(
            progress = Progress.NOT_STARTED,
            turns = emptyList(),
            currentPlayer = Player.ONE
        )
    }
}