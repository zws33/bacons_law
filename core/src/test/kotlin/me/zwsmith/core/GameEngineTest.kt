package me.zwsmith.core

import com.google.common.truth.Truth.assertThat
import org.junit.jupiter.api.Test

class GameEngineTest {
  private val tomHanks = Move.Actor(id = 1, displayText = "Tom Hanks")
  private val castAway = Move.Movie(id = 10, displayText = "Cast Away", castIds = setOf(1, 2))
  private val helenHunt = Move.Actor(id = 2, displayText = "Helen Hunt")
  private val toyStory = Move.Movie(id = 20, displayText = "Toy Story", castIds = setOf(1))
  private val outsider = Move.Actor(id = 99, displayText = "Unknown Actor")

  @Test
  fun `valid movie move appends to chain and switches player`() {
    val initialState = GameState.InProgress(
      moves = listOf(tomHanks),
      currentPlayerIndex = 1, // Player 2's turn
      playerCount = 2
    )

    val nextState = initialState.playMove(castAway) as GameState.InProgress

    assertThat(nextState.moves).containsExactly(tomHanks, castAway).inOrder()
    assertThat(nextState.currentPlayerIndex).isEqualTo(0) // Back to Player 1
  }

  @Test
  fun `valid actor move appends to chain and switches player`() {
    val initialState = GameState.InProgress(
      moves = listOf(tomHanks, castAway),
      currentPlayerIndex = 0, // Player 1's turn
      playerCount = 2
    )

    val nextState = initialState.playMove(helenHunt) as GameState.InProgress

    assertThat(nextState.moves).containsExactly(tomHanks, castAway, helenHunt).inOrder()
    assertThat(nextState.currentPlayerIndex).isEqualTo(1) // To Player 2
  }

  @Test
  fun `movie not featuring previous actor ends game`() {
    val initialState = GameState.InProgress(
      moves = listOf(helenHunt),
      currentPlayerIndex = 0, // Player 1's turn
      playerCount = 2
    )

    // Toy Story (castIds = {1}) does not feature Helen Hunt (id = 2)
    val result = initialState.playMove(toyStory) as GameState.GameOver

    assertThat(result.winnerIndex).isEqualTo(1) // Player 2 wins
    assertThat(result.losingMove).isEqualTo(toyStory)
  }

  @Test
  fun `actor not in previous movie ends game`() {
    val initialState = GameState.InProgress(
      moves = listOf(tomHanks, castAway),
      currentPlayerIndex = 0, // Player 1's turn
      playerCount = 2
    )

    // Outsider (id = 99) is not in Cast Away (castIds = {1, 2})
    val result = initialState.playMove(outsider) as GameState.GameOver

    assertThat(result.winnerIndex).isEqualTo(1) // Player 2 wins
    assertThat(result.losingMove).isEqualTo(outsider)
  }

  @Test
  fun `repeat actor ends game`() {
    val initialState = GameState.InProgress(
      moves = listOf(tomHanks, castAway, helenHunt),
      currentPlayerIndex = 1, // Player 2's turn
      playerCount = 2
    )

    val result = initialState.playMove(tomHanks) as GameState.GameOver

    assertThat(result.winnerIndex).isEqualTo(0) // Player 1 wins
    assertThat(result.losingMove).isEqualTo(tomHanks)
  }

  @Test
  fun `forfeit ends game, current player loses`() {
    val initialState = GameState.InProgress(
      moves = listOf(tomHanks),
      currentPlayerIndex = 1, // Player 2
      playerCount = 2
    )

    val result = initialState.forfeit()

    assertThat(result.winnerIndex).isEqualTo(0) // Player 1 wins
    assertThat(result.losingMove).isNull()
  }
}
