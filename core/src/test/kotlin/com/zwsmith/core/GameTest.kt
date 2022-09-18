package com.zwsmith.core

import io.kotest.core.spec.style.FunSpec
import io.kotest.matchers.shouldBe


class GameTest : FunSpec({

    context("Initialize game:") {
        val game = Game()
        with(game) {
            test("Verify initial state") {
                assert(gameState.progress == Game.Progress.NOT_STARTED)
                assert(getWinner() == null)
            }
            test("Playing valid first move advances game state") {
                val movieMove = Game.Move.Movie(
                    id = 1,
                    actors = listOf(9, 8, 7)
                )
                playMove(movieMove)
                gameState.progress shouldBe Game.Progress.IN_PROGRESS
                gameState.turns.size shouldBe 1
                gameState.turns.last().move shouldBe movieMove
                gameState.turns.last().player shouldBe Game.Player.ONE
            }
            test("Playing valid second move advances game state") {
                val actorMove = Game.Move.Actor(
                    id = 8,
                    movies = listOf(3, 4, 5)
                )
                playMove(actorMove)
                gameState.progress shouldBe Game.Progress.IN_PROGRESS
                gameState.turns.size shouldBe 2
                gameState.turns.last().move shouldBe actorMove
                gameState.turns.last().player shouldBe Game.Player.TWO
            }
            test("Playing invalid move ends game") {
                playMove(Game.Move.Movie(id = 6, emptyList()))
                gameState.progress shouldBe Game.Progress.COMPLETE
                getWinner() shouldBe Game.Player.TWO
            }
        }
    }
})