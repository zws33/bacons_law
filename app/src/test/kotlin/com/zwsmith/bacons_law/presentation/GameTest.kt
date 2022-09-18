package com.zwsmith.bacons_law.presentation

import io.kotest.core.spec.style.FunSpec
import io.kotest.matchers.shouldBe


class GameTest : FunSpec({

    test("Game play") {
        val game = Game()
        with(game) {
            assert(gameState.progress == Game.Progress.NOT_STARTED)
            assert(getWinner() == null)
            val movieMove = Game.GameMove.Movie(
                id = 1,
                actors = listOf(9, 8, 7)
            )
            playMove(movieMove)
            gameState.progress shouldBe Game.Progress.IN_PROGRESS
            gameState.turns.size shouldBe 1
            gameState.turns.last().move shouldBe movieMove
            gameState.turns.last().player shouldBe Game.Player.ONE
            val actorMove = Game.GameMove.Actor(
                id = 8,
                movies = listOf(3, 4, 5)
            )
            playMove(actorMove)
            gameState.progress shouldBe Game.Progress.IN_PROGRESS
            gameState.turns.size shouldBe 2
            gameState.turns.last().move shouldBe actorMove
            gameState.turns.last().player shouldBe Game.Player.TWO
            playMove(Game.GameMove.Movie(id = 6, emptyList()))
            gameState.progress shouldBe Game.Progress.COMPLETE
            getWinner() shouldBe Game.Player.TWO
        }
    }
})