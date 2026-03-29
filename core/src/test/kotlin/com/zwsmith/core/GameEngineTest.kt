package com.zwsmith.core

import io.kotest.core.spec.style.FunSpec

// API under test:
//   startGame(move: Move.Actor): GameState.InProgress
//   playMove(move: Move, state: GameState.InProgress): GameState
//   forfeit(state: GameState.InProgress): GameState.GameOver  ← not yet implemented

class GameEngineTest : FunSpec({

  // Fixtures
  // tomHanks is the starting actor (id=1)
  // castAway features tomHanks (id=1) and helenHunt (id=2) in its cast
  // helenHunt is a valid second actor to play after castAway
  // outsider is an actor NOT in castAway's cast — playing them after castAway should end the game
  // unrelatedMovie does NOT feature tomHanks — playing it after tomHanks should end the game
  val tomHanks = Move.Actor(id = 1, displayText = "Tom Hanks")
  val castAway = Move.Movie(id = 10, displayText = "Cast Away", castIds = setOf(1, 2))
  val helenHunt = Move.Actor(id = 2, displayText = "Helen Hunt")
  val outsider = Move.Actor(id = 99, displayText = "Unknown Actor")
  val unrelatedMovie = Move.Movie(id = 20, displayText = "Unrelated Movie", castIds = setOf(99))

  // --- Test 1 ---
  // startGame should place the starting actor as the only entry in moves
  test("startGame sets starting actor as first move") {
    // TODO
  }

  // --- Test 2 ---
  // After startGame, it is Player TWO's turn (Player ONE picked the starting actor)
  test("startGame sets current player to TWO") {
    // TODO
  }

  // --- Test 3 ---
  // Playing a movie that contains the previous actor is a valid move:
  // tomHanks → castAway (castAway.castIds contains tomHanks.id)
  // Expect: InProgress, moves grows by one, currentPlayer switches to ONE
  test("valid movie move appends to chain and switches player") {
    // TODO
  }

  // --- Test 4 ---
  // Playing an actor who appears in the previous movie is a valid move:
  // tomHanks → castAway → helenHunt (castAway.castIds contains helenHunt.id)
  // Expect: InProgress, moves grows to 3, currentPlayer switches back to TWO
  test("valid actor move appends to chain and switches player") {
    // TODO
  }

  // --- Test 5 ---
  // Playing a movie that does NOT feature the previous actor ends the game:
  // tomHanks → unrelatedMovie (unrelatedMovie.castIds does NOT contain tomHanks.id)
  // Expect: GameOver, loser = Player.TWO (the player who made the invalid move)
  test("movie not featuring previous actor ends game, current player loses") {
    // TODO
  }

  // --- Test 6 ---
  // Playing an actor NOT in the previous movie's cast ends the game:
  // tomHanks → castAway → outsider (castAway.castIds does NOT contain outsider.id)
  // Expect: GameOver, loser = Player.ONE
  test("actor not in previous movie ends game, current player loses") {
    // TODO
  }

  // --- Test 7 ---
  // Repeating an actor already in the chain ends the game:
  // tomHanks → castAway → tomHanks again
  // Expect: GameOver, loser = Player.ONE
  test("repeat actor ends game, current player loses") {
    // TODO
  }

  // --- Test 8 ---
  // Repeating a movie already in the chain ends the game.
  // Need a chain of at least 3 moves to have a movie to repeat:
  // tomHanks → castAway → helenHunt → castAway again
  // Expect: GameOver, loser = Player.TWO
  test("repeat movie ends game, current player loses") {
    // TODO
  }

  // --- Test 9 ---
  // TODO (after forfeit is implemented):
  // forfeit(state) should end the game with the current player as loser
  // test("forfeit ends game, current player loses") { }
})
