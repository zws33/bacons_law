package com.zwsmith.core

import com.google.common.truth.Truth.assertThat
import org.junit.jupiter.api.Test

class GameEngineTest {
  private val engine = GameEngine()
  private val tomHanks = Move.Actor(id = 1, displayText = "Tom Hanks")
  private val castAway = Move.Movie(id = 10, displayText = "Cast Away", castIds = setOf(1, 2))
  private val helenHunt = Move.Actor(id = 2, displayText = "Helen Hunt")
  private val outsider = Move.Actor(id = 99, displayText = "Unknown Actor")
  private val unrelatedMovie = Move.Movie(id = 20, displayText = "Unrelated Movie", castIds = setOf(99))

  @Test
  fun `startGame sets starting actor as first move`() {
    val state = engine.startGame(tomHanks)
    assertThat(state.moves).containsExactly(tomHanks)
  }

  @Test
  fun `startGame sets current player to TWO`() {
    val state = engine.startGame(tomHanks)
    assertThat(state.currentPlayer).isEqualTo(Player.TWO)
  }

  @Test
  fun `valid movie move appends to chain and switches player`() {
    val initialState = engine.startGame(tomHanks)
    val nextState =  engine.playMove(castAway, initialState) as GameState.InProgress

    assertThat(nextState.moves).containsExactly(tomHanks, castAway).inOrder()
    assertThat(nextState.currentPlayer).isEqualTo(Player.ONE)
  }

  @Test
  fun `valid actor move appends to chain and switches player`() {
    val state1 = engine.startGame(tomHanks)
    val state2 = engine.playMove(castAway, state1) as GameState.InProgress
    val state3 =  engine.playMove(helenHunt, state2) as GameState.InProgress

    assertThat(state3.moves).containsExactly(tomHanks, castAway, helenHunt).inOrder()
    assertThat(state3.currentPlayer).isEqualTo(Player.TWO)
  }

  @Test
  fun `movie not featuring previous actor ends game, current player loses`() {
    val initialState = engine.startGame(tomHanks)
    val result =  engine.playMove(unrelatedMovie, initialState) as GameState.GameOver

    assertThat(result.loser).isEqualTo(Player.TWO)
    assertThat(result.winner).isEqualTo(Player.ONE)
    assertThat(result.losingMove).isEqualTo(unrelatedMovie)
  }

  @Test
  fun `actor not in previous movie ends game, current player loses`() {
    val state1 = engine.startGame(tomHanks)
    val state2 =  engine.playMove(castAway, state1) as GameState.InProgress
    val result =  engine.playMove(outsider, state2) as GameState.GameOver

    assertThat(result.loser).isEqualTo(Player.ONE)
    assertThat(result.winner).isEqualTo(Player.TWO)
    assertThat(result.losingMove).isEqualTo(outsider)
  }

  @Test
  fun `repeat actor ends game, current player loses`() {
    val state1 = engine.startGame(tomHanks)
    val state2 =  engine.playMove(castAway, state1) as GameState.InProgress
    val result =  engine.playMove(tomHanks, state2) as GameState.GameOver

    assertThat(result.loser).isEqualTo(Player.ONE)
    assertThat(result.losingMove).isEqualTo(tomHanks)
  }

  @Test
  fun `repeat movie ends game, current player loses`() {
    val state1 = engine.startGame(tomHanks)
    val state2 =  engine.playMove(castAway, state1) as GameState.InProgress
    val state3 =  engine.playMove(helenHunt, state2) as GameState.InProgress
    val result =  engine.playMove(castAway, state3) as GameState.GameOver

    assertThat(result.loser).isEqualTo(Player.TWO)
    assertThat(result.losingMove).isEqualTo(castAway)
  }

  @Test
  fun `forfeit ends game, current player loses`() {
    val state = engine.startGame(tomHanks)
    val result =  engine.forfeit(state)

    assertThat(result.loser).isEqualTo(Player.TWO)
    assertThat(result.winner).isEqualTo(Player.ONE)
    assertThat(result.losingMove).isNull()
  }
}
