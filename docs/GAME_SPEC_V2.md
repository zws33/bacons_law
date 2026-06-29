# Bacon's Law — Game Spec v2

This document is the authoritative specification for the pure game engine (the Kotlin `:core` module). It supersedes the game rules section of [GAME_SPEC.md](GAME_SPEC.md) for implementation purposes; that document remains a reference for product intent and out-of-scope decisions. Its data model matches `core/src/main/kotlin/me/zwsmith/core/GameEngine.kt` directly (`Move.Movie.castIds: Set<Int>` is the validation contract).

**Scope:** This document specifies the pure game engine only — state transitions, validation, and end conditions. It makes no assumptions about network transport, UI, or persistence. The engine receives moves and returns new state. It performs no I/O.

---

## Data Model

### Move

A move is one link in the chain. There are two types:

**Actor**
- `id: int` — TMDB person ID, used as the canonical identifier
- `display_text: str` — human-readable name (for display only, not used in validation)
- `image_path: str | None` — optional poster/photo path (display only)

**Movie**
- `id: int` — TMDB movie ID, used as the canonical identifier
- `display_text: str` — human-readable title (display only)
- `cast_ids: set[int]` — set of TMDB person IDs for all credited cast members; **this is the validation contract**
- `image_path: str | None` — optional poster path (display only)
- `release_year: str | None` — optional year (display only)

`cast_ids` is the only field that drives validation logic. All other fields are metadata carried for the benefit of the UI layer.

### GameState

The engine has two terminal states:

**InProgress**
- `moves: list[Move]` — the chain in submission order; may be empty at game start
- `current_player_index: int` — zero-based index of the player whose turn it is
- `player_count: int` — total number of players; must be ≥ 2

**GameOver**
- `winner_index: int` — zero-based index of the winning player
- `chain: list[Move]` — the valid chain at the time the game ended; does **not** include the losing move
- `losing_move: Move | None` — the move that ended the game; `None` if the game ended by forfeit

### Engine Interface

```
play_move(state: InProgress, move: Move) -> GameState
forfeit(state: InProgress) -> GameOver
```

`play_move` returns either `InProgress` (valid move accepted) or `GameOver` (invalid move rejected). `forfeit` always returns `GameOver`.

---

## Rules

### R1 — First move is always accepted

When the chain is empty (`moves == []`), `play_move` accepts any move unconditionally and appends it to the chain. No connection validation or repeat detection is performed.

**Rationale:** The first move has no predecessor to connect to. The constraint that the first move must be an Actor is a UI-layer concern, not an engine rule.

### R2 — Valid connection: Actor after Movie

A Move.Actor is a valid connection after a Move.Movie when:

```
move.id in previous_move.cast_ids
```

The actor's TMDB ID must appear in the movie's cast ID set.

### R3 — Valid connection: Movie after Actor

A Move.Movie is a valid connection after a Move.Actor when:

```
previous_move.id in move.cast_ids
```

The previous actor's TMDB ID must appear in the movie's cast ID set.

### R4 — Same-type consecutive moves are always invalid

An Actor following an Actor, or a Movie following a Movie, is always an invalid connection regardless of IDs. The chain must strictly alternate types.

### R5 — Repeat detection

A move is a repeat if a move of the same type with the same ID already exists anywhere in the chain:

```
# For an Actor move:
any(m.id == move.id for m in chain if isinstance(m, Actor))

# For a Movie move:
any(m.id == move.id for m in chain if isinstance(m, Movie))
```

ID uniqueness is enforced within a type. An Actor ID and a Movie ID may share the same integer value without triggering repeat detection — they are different entity types.

### R6 — Invalid move ends the game

If `play_move` is called with a non-empty chain and either:
- the move is a repeat (R5), **or**
- the move is not a valid connection to the previous move (R2, R3, R4)

...then the game ends immediately. The current player loses; the previous player wins.

The invalid move is recorded in `GameOver.losing_move`. The `chain` in `GameOver` contains the moves that were accepted before this move — it does not include the losing move.

Repeat detection takes priority: if a move is both a repeat and an invalid connection, it is treated as a repeat. (In practice this distinction doesn't matter — both paths produce the same `GameOver` with the same loser.)

### R7 — Forfeit ends the game

`forfeit` ends the game immediately. The current player (the one whose turn it is) loses; the previous player wins. `GameOver.losing_move` is `None`.

### R8 — Winner determination

The winner is always the previous player — the one who was NOT responsible for the losing move or forfeit:

```
winner_index = (current_player_index - 1 + player_count) % player_count
```

For a 2-player game this simplifies to: the player who did not just lose.

### R9 — Player rotation

After a valid move is accepted, the turn advances to the next player:

```
next_player_index = (current_player_index + 1) % player_count
```

Rotation wraps around; after the last player it returns to player 0.

### R10 — Engine performs no I/O

The engine is pure. It does not call TMDB, Redis, Postgres, or any network resource. All data required for validation (`cast_ids`) must be populated by the caller before passing a move to `play_move`.

---

## Engine Boundary: What the Engine Does Not Enforce

These constraints are required by the game design but are enforced by the caller (UI or session layer), not the engine:

| Constraint | Where enforced |
|---|---|
| First move must be an Actor | UI / session layer |
| Move type must alternate (Actor, then Movie, then Actor...) | UI / session layer presents the correct search type per turn; engine rejects wrong-type moves via R4 as a safety net |
| `cast_ids` must be accurate and complete | Caller fetches credits from TMDB before constructing a Movie move |
| Player count is exactly 2 for MVP | Session layer; engine supports N ≥ 2 |

---

## Test Cases

All tests operate on the engine interface only: `play_move` and `forfeit`. No network or I/O.

### Fixtures

```
TOM_HANKS   = Actor(id=1,  display_text="Tom Hanks")
HELEN_HUNT  = Actor(id=2,  display_text="Helen Hunt")
OUTSIDER    = Actor(id=99, display_text="Unknown Actor")

CAST_AWAY   = Movie(id=10, display_text="Cast Away",  cast_ids={1, 2})
TOY_STORY   = Movie(id=20, display_text="Toy Story",  cast_ids={1})
UNRELATED   = Movie(id=30, display_text="Unrelated",  cast_ids={99})
```

---

### TC-01 — Valid movie move: appended to chain, player advances

```
Given:
  state = InProgress(
    moves = [TOM_HANKS],
    current_player_index = 1,
    player_count = 2
  )

When:
  result = play_move(state, CAST_AWAY)
  # Cast Away (cast_ids={1,2}) contains Tom Hanks (id=1) ✓

Then:
  result is InProgress
  result.moves == [TOM_HANKS, CAST_AWAY]
  result.current_player_index == 0   # wrapped back to player 0
```

### TC-02 — Valid actor move: appended to chain, player advances

```
Given:
  state = InProgress(
    moves = [TOM_HANKS, CAST_AWAY],
    current_player_index = 0,
    player_count = 2
  )

When:
  result = play_move(state, HELEN_HUNT)
  # Cast Away (cast_ids={1,2}) contains Helen Hunt (id=2) ✓

Then:
  result is InProgress
  result.moves == [TOM_HANKS, CAST_AWAY, HELEN_HUNT]
  result.current_player_index == 1
```

### TC-03 — Movie not featuring previous actor: game over

```
Given:
  state = InProgress(
    moves = [HELEN_HUNT],
    current_player_index = 0,
    player_count = 2
  )

When:
  result = play_move(state, TOY_STORY)
  # Toy Story (cast_ids={1}) does NOT contain Helen Hunt (id=2) ✗

Then:
  result is GameOver
  result.winner_index == 1        # player 1 wins; player 0 loses
  result.losing_move == TOY_STORY
  result.chain == [HELEN_HUNT]    # losing move not in chain
```

### TC-04 — Actor not in previous movie: game over

```
Given:
  state = InProgress(
    moves = [TOM_HANKS, CAST_AWAY],
    current_player_index = 0,
    player_count = 2
  )

When:
  result = play_move(state, OUTSIDER)
  # Cast Away (cast_ids={1,2}) does NOT contain OUTSIDER (id=99) ✗

Then:
  result is GameOver
  result.winner_index == 1
  result.losing_move == OUTSIDER
  result.chain == [TOM_HANKS, CAST_AWAY]
```

### TC-05 — Repeat actor: game over

```
Given:
  state = InProgress(
    moves = [TOM_HANKS, CAST_AWAY, HELEN_HUNT],
    current_player_index = 1,
    player_count = 2
  )

When:
  result = play_move(state, TOM_HANKS)
  # TOM_HANKS (id=1) already in chain ✗

Then:
  result is GameOver
  result.winner_index == 0        # player 0 wins; player 1 loses
  result.losing_move == TOM_HANKS
  result.chain == [TOM_HANKS, CAST_AWAY, HELEN_HUNT]
```

### TC-06 — Repeat movie: game over

```
Given:
  state = InProgress(
    moves = [TOM_HANKS, CAST_AWAY, HELEN_HUNT, TOY_STORY],
    current_player_index = 0,
    player_count = 2
  )
  # Note: TOY_STORY is already in the chain

When:
  result = play_move(state, CAST_AWAY)
  # CAST_AWAY (id=10) already in chain ✗

Then:
  result is GameOver
  result.winner_index == 1
  result.losing_move == CAST_AWAY
  result.chain == [TOM_HANKS, CAST_AWAY, HELEN_HUNT, TOY_STORY]
```

### TC-07 — Forfeit: current player loses, losingMove is None

```
Given:
  state = InProgress(
    moves = [TOM_HANKS],
    current_player_index = 1,
    player_count = 2
  )

When:
  result = forfeit(state)

Then:
  result is GameOver
  result.winner_index == 0        # player 1 forfeited; player 0 wins
  result.losing_move is None
  result.chain == [TOM_HANKS]
```

### TC-08 — First move on empty chain: always accepted

```
Given:
  state = InProgress(
    moves = [],
    current_player_index = 0,
    player_count = 2
  )

When:
  result = play_move(state, TOM_HANKS)
  # No previous move to validate against

Then:
  result is InProgress
  result.moves == [TOM_HANKS]
  result.current_player_index == 1
```

### TC-09 — Actor after actor (same-type consecutive): game over

```
Given:
  state = InProgress(
    moves = [TOM_HANKS],
    current_player_index = 1,
    player_count = 2
  )

When:
  result = play_move(state, HELEN_HUNT)
  # Previous move is an Actor; submitting another Actor is always invalid

Then:
  result is GameOver
  result.winner_index == 0
  result.losing_move == HELEN_HUNT
```

### TC-10 — Movie after movie (same-type consecutive): game over

```
Given:
  state = InProgress(
    moves = [TOM_HANKS, CAST_AWAY],
    current_player_index = 0,
    player_count = 2
  )

When:
  result = play_move(state, TOY_STORY)
  # Previous move is a Movie; submitting another Movie is always invalid

Then:
  result is GameOver
  result.winner_index == 1
  result.losing_move == TOY_STORY
```

### TC-11 — Cross-type ID collision is not a repeat

```
Given:
  # Actor and Movie that happen to share the same integer ID
  ACTOR_ID_10 = Actor(id=10, display_text="Some Actor")
  MOVIE_ID_10 = Movie(id=10, display_text="Some Movie", cast_ids={10})

  state = InProgress(
    moves = [ACTOR_ID_10, MOVIE_ID_10],
    current_player_index = 0,
    player_count = 2
  )

When:
  result = play_move(state, ACTOR_ID_10)
  # ACTOR_ID_10 (id=10) is already in the chain as an Actor → this IS a repeat

# Separate assertion: submitting a fresh Actor with id=10 when only Movie id=10
# is in the chain is NOT a repeat.

  state2 = InProgress(
    moves = [ACTOR_ID_10, MOVIE_ID_10],
    current_player_index = 0,
    player_count = 2
  )
  fresh_actor = Actor(id=10, display_text="Same ID Different Entity")

  # This IS a repeat because ACTOR_ID_10 (Actor, id=10) is already in the chain.
  # A Movie with id=10 and an Actor with id=10 are separate entities — but
  # fresh_actor shares the id with ACTOR_ID_10 (same type), so it IS a repeat.

# Cleaner version of the cross-type test:
  state3 = InProgress(
    moves = [MOVIE_ID_10],          # only a Movie with id=10 in chain
    current_player_index = 0,
    player_count = 2
  )
  actor_same_id = Actor(id=10, display_text="Actor whose id matches a movie already in chain")

When:
  result3 = play_move(state3, actor_same_id)
  # Previous move is a Movie; actor_same_id is an Actor — same-type check:
  # no Actors in chain with id=10, so NOT a repeat.
  # Connection check: MOVIE_ID_10.cast_ids = {10}, actor_same_id.id = 10 → VALID.

Then:
  result3 is InProgress   # valid connection, not a repeat
```

### TC-12 — Player rotation wraps correctly (3-player example)

```
Given:
  state = InProgress(
    moves = [TOM_HANKS],
    current_player_index = 2,   # player 2's turn in a 3-player game
    player_count = 3
  )

When:
  result = play_move(state, CAST_AWAY)   # valid connection

Then:
  result is InProgress
  result.current_player_index == 0    # wraps from 2 → 0

# Winner determination on forfeit in same setup:
When:
  result2 = forfeit(state)

Then:
  result2 is GameOver
  result2.winner_index == 1   # previous of 2 in 3-player = (2-1+3)%3 = 1
```

---

## Summary Table

| TC | Scenario | End state | Notes |
|---|---|---|---|
| 01 | Valid movie after actor | InProgress | chain grows, player advances |
| 02 | Valid actor after movie | InProgress | chain grows, player advances |
| 03 | Movie — actor not in cast | GameOver | invalid connection |
| 04 | Actor — not in movie cast | GameOver | invalid connection |
| 05 | Repeat actor | GameOver | same id, same type |
| 06 | Repeat movie | GameOver | same id, same type |
| 07 | Forfeit | GameOver | losing_move is None |
| 08 | First move (empty chain) | InProgress | always accepted |
| 09 | Actor after actor | GameOver | same-type consecutive |
| 10 | Movie after movie | GameOver | same-type consecutive |
| 11 | Cross-type ID collision | InProgress | different types, not a repeat |
| 12 | Player rotation wrap | InProgress / GameOver | modular arithmetic |
