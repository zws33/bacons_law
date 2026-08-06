# Bacon's Law — Round Engine Conformance Spec

**Status:** Authoritative for round-engine behavior. Language- and framework-agnostic.

This document defines the minimum behavior any Bacon's Law **round engine** must exhibit, expressed as
rules plus a numbered conformance suite. It exists so that engine behavior survives a change of
language, framework, or module layout — the application stack is provisional
([AGENTS.md](../AGENTS.md)), the rules below are not.

It is derived by reconciling three sources: the `movie-actor-chain-game` skill (domain rules), the
Kotlin `:core` implementation and its test suite (a prototype, not authority), and the test scenarios
in [issue #17](https://github.com/zws33/bacons_law/issues/17). Where they disagreed, the reconciliation
is recorded in [Divergences from source material](#divergences-from-source-material).

---

## Scope: the round engine, not the match

The system has two layers. This document specifies **only the lower one**.

**The round engine** builds one chain. It accepts an opening move, rotates turns among N players,
validates each submission against the previous move, and — when a player submits an invalid move or
gives up — ends the round and reports **who failed**. That is the whole of its job.

**The match layer** owns everything after that: strike accounting, whether a strike limit eliminates a
player or ends the match, standings across an ongoing series, game-mode configuration, who opens the
next round, whether entities used in earlier rounds stay available, and whether the mode names a
winner at all. It is a real part of the product and is
**deliberately out of scope here** — the permutations are many and configurable, and none of them
change how a turn is evaluated.

**The round engine names a loser, never a winner.** The aim of the game is to not fail a turn, so
every round has exactly one unambiguous loser: the player on turn when the chain broke. It does not
have a natural winner — every player who did not fail is simply not the loser, and singling out
whoever happened to play the last valid move is an arbitrary convention. If a mode wants that, the
match layer can derive it (see [R8](#r8--loser-determination)); the engine must not assert it.

This split is why multiplayer costs the engine almost nothing. Supporting N > 2 is a **day-one
requirement**, and at the round layer it reduces to rotating turns modulo N and reporting an index.

---

## How to use this document

**To implement an engine:** satisfy every rule in [Rules](#rules). The
[Engine boundary](#engine-boundary) table lists what you must *not* enforce here.

**To generate a test suite:** each `TC-nn` in [Conformance suite](#conformance-suite) becomes exactly
one test. Translate the fixtures once into a shared fixture module, then translate each case's
GIVEN/WHEN/THEN literally. Keep the `TC-nn` identifier in the test name so coverage stays traceable
to this document. Cases marked **[static]** may be satisfied by the type system instead of a runtime
test — see [TC-24](#tc-24--operations-are-inapplicable-to-a-terminal-state).

**To evaluate a proposed design:** a design that cannot satisfy these cases without an I/O call,
a network hop, or a per-turn external lookup violates the binding architecture boundaries in
[AGENTS.md](../AGENTS.md) regardless of how it scores otherwise.

**What this document is not:** it does not specify transport, persistence, UI, identity, time
controls, scoring, or match structure. It specifies one round, played by pure state transitions.

---

## Vocabulary

The document uses the `movie-actor-chain-game` skill's terms. The Kotlin prototype's names are mapped
here only so the old code is readable; prefer the **Spec term** column in new code.

| Spec term | `movie-actor-chain-game` skill | Kotlin `:core` (prototype) |
|---|---|---|
| Move | Entity | `Move` |
| Move type | Entity Type | `Move.Actor` / `Move.Movie` |
| Chain | The round's sequence of turns | `moves` / `chain` |
| Previous move | Prompt Entity | `moves.last()` |
| Required type | Required Type | implicit — derived from previous move |
| Round | Round | `GameState` (misnamed) |
| Round over | Round end | `GameState.GameOver` (misnamed) |
| Loser | The failing player | `winnerIndex` (inverted — see [Divergences](#divergences-from-source-material)) |

**One round is one chain.** A match is a series of rounds; that layer exists but is specified
elsewhere.

---

## Data model

Notation is pseudo-code. `?` marks an optional field. Translate to whatever the target language's
idiom is (sum types, tagged unions, discriminated records).

```
type EntityId = String
    # Opaque, non-empty. The engine never parses, orders, or arithmetics on it.
    # Project binding: a Wikidata QID, e.g. "Q23844".
    # Do NOT re-map to integers — ID adaptation is a loader concern (AGENTS.md).

Actor:
    id:           EntityId
    displayText:  String
    imagePath:    String?          # display only

Movie:
    id:           EntityId
    displayText:  String
    castIds:      Set<EntityId>    # THE VALIDATION CONTRACT
    imagePath:    String?          # display only
    releaseYear:  String?          # display only

Move = Actor | Movie
```

`castIds` is the only field that participates in validation. Everything else is metadata carried for
the presentation layer — see [R12](#r12--identity-is-the-id-alone).

```
InProgress:
    moves:               List<Move>    # the chain, in submission order; may be empty
    currentPlayerIndex:  Int           # zero-based; the player to move
    playerCount:         Int           # >= 2; no upper bound imposed by the engine
    excludedActorIds:    Set<EntityId> # default empty; seeded by the match layer
    excludedMovieIds:    Set<EntityId> # default empty; seeded by the match layer

RoundOver:
    loserIndex:   Int                  # the player who failed
    chain:        List<Move>           # accepted moves; EXCLUDES the losing move
    losingMove:   Move?                # null when the round ended by giving up

RoundState = InProgress | RoundOver
```

**`RoundOver` carries no winner.** See [R8](#r8--loser-determination) and
[S3](#s3--the-round-result-names-no-winner-structural-not-a-test-case).

**The exclusion sets are how a match forbids reuse across rounds.** Both default to empty, which is
the default mode: a new round starts with every entity available again. A mode that forbids reuse for
the whole match seeds them with everything played in earlier rounds. The engine does not know which
mode is in play — it reads two sets and applies [R5](#r5--repeat-detection-is-per-type). Populating
them is the match layer's job; see [Engine boundary](#engine-boundary).

**Player indices are positions in a roster fixed for the round.** The engine never adds or removes
players mid-round, so an index is stable from the opening move to the round's end. A match layer that
drops an eliminated player does so *between* rounds, by starting the next round with a smaller
`playerCount`.

## Operations

```
playMove(state: InProgress, move: Move) -> RoundState    # InProgress or RoundOver
forfeit(state: InProgress)              -> RoundOver
```

Both are pure functions of their arguments. Neither performs I/O. Neither mutates its input.

`forfeit` means "the player on turn cannot continue this round" — an explicit give-up, or whatever the
session layer maps a timeout to. It concedes **the round, not the match**; a player quitting the match
outright is a match-layer event that happens to end the current round this way.

---

## Rules

### R1 — The opening move is not connection-checked

When `moves` is empty, `playMove` performs no connection check and no type check: an opening move may
be either an Actor or a Movie, and any entity is a legal opener.

*Rationale:* there is no predecessor to connect to, and no earlier move to alternate from.
"The first move must be an Actor" is not a rule of this game; if some mode wants it, that is a
caller-layer constraint — see [Engine boundary](#engine-boundary).

**[R5](#r5--repeat-detection-is-per-type) still applies.** On an empty chain with empty exclusion sets
it is vacuous — nothing has been played, so nothing can be a repeat — which is why the opener is
accepted unconditionally in the default mode. It is *not* vacuous when the match layer has seeded
exclusions: an entity banned for the match cannot be smuggled in as a round's opening move. R1
exempts the opener from the checks that need a predecessor, not from every check.

### R2 — Actor after Movie

An `Actor` following a `Movie` is a valid connection iff:

```
move.id ∈ previousMove.castIds
```

### R3 — Movie after Actor

A `Movie` following an `Actor` is a valid connection iff:

```
previousMove.id ∈ move.castIds
```

### R4 — Same-type consecutive moves are always invalid

`Actor` after `Actor`, or `Movie` after `Movie`, is invalid regardless of IDs. The chain strictly
alternates.

### R5 — Repeat detection is per-type

A move is a repeat iff a move **of the same type** with the same `id` already appears anywhere in the
chain, or its `id` appears in the exclusion set for its type:

```
isRepeat(move, state) =
    match move:
        Actor -> move.id ∈ state.excludedActorIds
                 or any(m.id == move.id for m in state.moves where m is Actor)
        Movie -> move.id ∈ state.excludedMovieIds
                 or any(m.id == move.id for m in state.moves where m is Movie)
```

**Within a round, the same move may never appear twice.** This is a game rule, not a bug.

Uniqueness is scoped within a type, for both the chain and the exclusion sets. An Actor and a Movie
sharing an `id` do not collide, and an id in `excludedMovieIds` does not bar an Actor with that id.

**Across rounds, reuse is allowed by default.** Empty exclusion sets mean a fresh round makes every
entity available again. A mode that forbids reuse for the whole match seeds the sets from earlier
rounds; the engine's rule is unchanged either way. Which mode applies is chosen in game settings
before play and is not the engine's concern.

### R6 — An invalid move ends the round

The round ends immediately if the move is a repeat ([R5](#r5--repeat-detection-is-per-type)), **or** —
when the chain is non-empty — is not a valid connection
([R2](#r2--actor-after-movie)/[R3](#r3--movie-after-actor)/[R4](#r4--same-type-consecutive-moves-are-always-invalid)).

Note the asymmetry, which follows from [R1](#r1--the-opening-move-is-not-connection-checked): the
connection check requires a predecessor and so is skipped on an empty chain, while the repeat check
always runs. On an empty chain with no exclusions the repeat check cannot fail, so an opening move is
rejected only in a mode that seeded exclusions
([TC-30](#tc-30--exclusions-apply-to-the-opening-move)).

`RoundOver.losingMove` is the rejected move. `RoundOver.chain` holds the moves accepted **before** it —
the losing move is never appended.

### R7 — Giving up ends the round

`forfeit` ends the round immediately. `RoundOver.losingMove` is null and `RoundOver.chain` is the chain
unchanged.

### R8 — Loser determination

```
loserIndex = currentPlayerIndex
```

The player on turn is the player who failed, whether by an invalid move
([R6](#r6--an-invalid-move-ends-the-round)) or by giving up ([R7](#r7--giving-up-ends-the-round)).
This holds at every `playerCount` — there is no arithmetic and no special case for N > 2.

**The engine names no winner and no runner-up, and imposes no ordering on the players who did not
fail.** A mode that wants "the player who made the last valid move wins" can compute
`(loserIndex - 1 + playerCount) % playerCount` at the match layer; that it is derivable from the round
result is precisely why it does not belong in the round result.

### R9 — Player rotation

After an accepted move:

```
nextPlayerIndex = (currentPlayerIndex + 1) % playerCount
```

Rotation wraps, at any `playerCount >= 2`. No player is skipped: a round ends at the first failure, so
no player is ever removed mid-round.

### R10 — The engine is pure

No network, no storage, no platform dependency, no clock, no randomness. `playMove` and `forfeit` are
deterministic functions of their arguments and do not mutate them. All data needed for validation is
supplied by the caller before the move reaches the engine.

### R11 — Connection is evaluated against the immediately preceding move only

Validity depends on `moves.last()` and nothing earlier. A move that would connect to some other
element of the chain but not the last one is invalid.

### R12 — Identity is the ID alone

Two moves of the same type with the same `id` are the same entity for every purpose, whatever their
`displayText`, `imagePath`, `releaseYear`, or `castIds`. Metadata never affects validation.

### R13 — Invalid state and move construction is rejected

Construction must reject, raising a validation error:

- `InProgress` with `playerCount < 2`
- `InProgress` with `currentPlayerIndex < 0` or `currentPlayerIndex >= playerCount`
- `Actor` or `Movie` with an empty or blank `id`
- `Movie` with an empty or blank member in `castIds`

Rejection happens **at construction**, not deferred to `playMove`. An invalid state must not be
representable.

`Movie.castIds` being an *empty set* is valid — it is legal data, not malformation. Such a movie
simply connects to no actor in either direction. (The ETL's `min_cast` floor means it should not
occur in practice; the engine must not depend on that.)

### R14 — Operations are inapplicable to terminal states

`playMove` and `forfeit` accept only `InProgress`. In a language whose type system can express this,
the signature must enforce it statically and no runtime check is required. Otherwise, invoking either
on a `RoundOver` must raise a programming error.

### R15 — Malformed input is an error, never a round outcome

Violations of [R13](#r13--invalid-state-and-move-construction-is-rejected) and
[R14](#r14--operations-are-inapplicable-to-terminal-states) must surface as errors distinguishable
from normal results. They must never be reported as a `RoundOver`.

*Rationale:* a malformed input silently resolving to a loss would end real rounds incorrectly and
charge a strike to a player who did nothing wrong.

---

## Engine boundary

Required by the game, enforced elsewhere. An engine that enforces these is over-scoped.

| Constraint | Enforced by |
|---|---|
| What a round loss costs — strikes, elimination, match end | Match layer |
| Strike limits, standings, ranking across an ongoing series | Match layer |
| Game-mode configuration, fixed before the round starts | Match layer |
| Naming a winner, if the mode defines one | Match layer ([R8](#r8--loser-determination)) |
| Who opens the next round, and with which roster | Match layer; it passes the next round a `playerCount` |
| Whether entities reuse across rounds — and seeding `excludedActorIds` / `excludedMovieIds` accordingly | Match layer; the engine applies the sets it is given ([R5](#r5--repeat-detection-is-per-type)) |
| Requiring the opening move to be an Actor, if a mode wants it | Caller (session / UI layer) |
| The player is offered the correct entity type each turn | Caller presents the right search mode; [R4](#r4--same-type-consecutive-moves-are-always-invalid) is the engine's backstop |
| `castIds` is accurate and complete | Caller populates from the in-memory graph before constructing the move |
| Name resolution, typos, disambiguation | Caller, before a `Move` exists |
| Mapping a deadline expiry or an abandonment onto a round result | Session layer; it calls `forfeit` ([ADR 012](DECISIONS.md), as amended by [ADR 018](DECISIONS.md) — one deadline model, no running clock) |
| Detecting that the player on turn has no legal move at all | Session layer; it holds the graph. The engine cannot see it when the chain head is an Actor — see [Open questions](#open-questions) |
| Persistence, transport, presence | Session layer |

**"Appeared in" is defined by the graph, not by the engine.** `castIds` reflects what the ETL
artifact carries — truthy `wdt:P161`, capped at `cast_cap`. A real but absent cast member is not a
legal move. That is a data dial, not an engine rule.

**Move attribution is derivable, not stored.** `RoundOver.chain` records moves, not who played them.
A caller that needs per-move attribution computes it from the round's opening player index and
[R9](#r9--player-rotation): move `i` was played by `(openingPlayerIndex + i) % playerCount`. The match
layer knows the opening index because it started the round.

---

## Conformance suite

**Fixture identifiers are synthetic.** The QIDs below are QID-*shaped* placeholders, not real
Wikidata identifiers, and the display names are for readability only ([R12](#r12--identity-is-the-id-alone)).
Do not resolve them against the graph artifact; do not treat any of this as data.

```
TOM_HANKS    = Actor(id="Q1",  displayText="Tom Hanks")
HELEN_HUNT   = Actor(id="Q2",  displayText="Helen Hunt")
BILL_PAXTON  = Actor(id="Q3",  displayText="Bill Paxton")
EARLY_ONLY   = Actor(id="Q98", displayText="Actor in an earlier movie only")
OUTSIDER     = Actor(id="Q99", displayText="Unknown Actor")

CAST_AWAY    = Movie(id="Q10", displayText="Cast Away", castIds={"Q1", "Q2"})
TOY_STORY    = Movie(id="Q20", displayText="Toy Story", castIds={"Q1"})
UNRELATED    = Movie(id="Q30", displayText="Unrelated", castIds={"Q99", "Q1", "Q98"})
EMPTY_CAST   = Movie(id="Q40", displayText="No Cast On Record", castIds={})
TWISTER      = Movie(id="Q50", displayText="Twister",   castIds={"Q2", "Q3"})
APOLLO       = Movie(id="Q60", displayText="Apollo 13", castIds={"Q1", "Q3"})
```

A six-move chain used by several cases below, valid at every step:

```
LONG_CHAIN = [TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER, BILL_PAXTON, APOLLO]
#             Q1      ->  {Q1,Q2}  ->  Q2      ->  {Q2,Q3} ->  Q3      ->  {Q1,Q3}
```

Every case asserting `RoundOver` must also assert that `chain` excludes the losing move
([R6](#r6--an-invalid-move-ends-the-round)).

**Two properties hold across the suite; preserve both when translating.**

*Every GIVEN chain is legally reachable.* Each fixture chain could have been produced by playing its
moves in order from an empty chain — every adjacent pair alternates type and connects. A case that
asserts behavior from an unreachable chain proves nothing about a real round. `currentPlayerIndex` is
independent: the engine keeps no record of who played which move, so any in-range index is a valid
state to test, and several cases set one that does not match the chain's length.

*Each case isolates one rule.* Where a move could be rejected for more than one reason, the fixtures
are chosen so exactly one applies — a repeat case is a valid connection of the correct type, so an
engine with no repeat detection fails it rather than passing by accident.
[TC-20](#tc-20--repeat-and-connection-failure-produce-identical-outcomes) is the sole exception, and
stacking two causes is the behavior it exists to pin. Do not "simplify" a fixture during translation;
the specific IDs are load-bearing.

---

### Group A — Chain construction and turn advance

#### TC-01 — Valid movie after actor

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=1, playerCount=2)
WHEN   result = playMove(state, CAST_AWAY)          # "Q1" ∈ {"Q1","Q2"}
THEN   result is InProgress
       result.moves == [TOM_HANKS, CAST_AWAY]
       result.currentPlayerIndex == 0
```

#### TC-02 — Valid actor after movie

```
GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, HELEN_HUNT)         # "Q2" ∈ {"Q1","Q2"}
THEN   result is InProgress
       result.moves == [TOM_HANKS, CAST_AWAY, HELEN_HUNT]
       result.currentPlayerIndex == 1
```

#### TC-08 — The opening move is accepted on an empty chain

```
GIVEN  state = InProgress(moves=[], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOM_HANKS)
THEN   result is InProgress
       result.moves == [TOM_HANKS]
       result.currentPlayerIndex == 1
```

#### TC-13 — The opening move may be a movie

Pins [R1](#r1--the-opening-move-is-not-connection-checked): the engine imposes no type constraint on
the opener. Either type opens a round.

```
GIVEN  state = InProgress(moves=[], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, CAST_AWAY)
THEN   result is InProgress
       result.moves == [CAST_AWAY]
       result.currentPlayerIndex == 1
```

#### TC-25 — A full round plays from an empty chain

Every other case constructs its `InProgress` by hand. This one is the only case that feeds each
result back in as the next input, so it is what catches a transition that returns a subtly wrong
state — a dropped move, a stale index, a chain rebuilt in the wrong order. It also proves
`LONG_CHAIN` is legally reachable, which the rest of the suite assumes.

```
GIVEN  state = InProgress(moves=[], currentPlayerIndex=0, playerCount=2)
WHEN   each move of LONG_CHAIN is played in order, each result becoming the next input
THEN   every intermediate result is InProgress
       currentPlayerIndex after each move is 1, 0, 1, 0, 1, 0 in that order
       final.moves == LONG_CHAIN
       final.playerCount == 2
```

---

### Group B — Connection validation

#### TC-03 — Movie whose cast excludes the previous actor

```
GIVEN  state = InProgress(moves=[HELEN_HUNT], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOY_STORY)          # "Q2" ∉ {"Q1"}
THEN   result is RoundOver
       result.loserIndex == 0
       result.losingMove == TOY_STORY
       result.chain == [HELEN_HUNT]
```

#### TC-04 — Actor absent from the previous movie's cast

```
GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, OUTSIDER)           # "Q99" ∉ {"Q1","Q2"}
THEN   result is RoundOver
       result.loserIndex == 0
       result.losingMove == OUTSIDER
       result.chain == [TOM_HANKS, CAST_AWAY]
```

#### TC-09 — Actor after actor

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=1, playerCount=2)
WHEN   result = playMove(state, HELEN_HUNT)
THEN   result is RoundOver
       result.loserIndex == 1
       result.losingMove == HELEN_HUNT
       result.chain == [TOM_HANKS]
```

#### TC-10 — Movie after movie

```
GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOY_STORY)
THEN   result is RoundOver
       result.loserIndex == 0
       result.losingMove == TOY_STORY
       result.chain == [TOM_HANKS, CAST_AWAY]
```

Note this case is invalid on type grounds ([R4](#r4--same-type-consecutive-moves-are-always-invalid))
even though `TOY_STORY.castIds` contains `"Q1"`. An implementation that checked cast membership
without checking type would wrongly accept it.

#### TC-14 — Connection is evaluated against the immediately preceding move only

`EARLY_ONLY` is in the cast of `UNRELATED`, which sits earlier in the chain, but not in the cast of
`CAST_AWAY`, which is last. It is not a repeat, so the only thing that can reject it is
[R11](#r11--connection-is-evaluated-against-the-immediately-preceding-move-only).

```
GIVEN  state = InProgress(
           moves=[OUTSIDER, UNRELATED, TOM_HANKS, CAST_AWAY],
           currentPlayerIndex=0, playerCount=2)
       # Q99 -> {Q99,Q1,Q98} -> Q1 -> {Q1,Q2} : valid at every step

WHEN   result = playMove(state, HELEN_HUNT)
THEN   result is InProgress                          # "Q2" ∈ CAST_AWAY.castIds

GIVEN  the same state
WHEN   result = playMove(state, EARLY_ONLY)
THEN   result is RoundOver                           # "Q98" ∈ UNRELATED.castIds but ∉ CAST_AWAY.castIds
       result.loserIndex == 0
       result.losingMove == EARLY_ONLY
       result.chain == [OUTSIDER, UNRELATED, TOM_HANKS, CAST_AWAY]
```

#### TC-17 — A movie with an empty cast connects to nothing

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, EMPTY_CAST)
THEN   result is RoundOver                           # "Q1" ∉ {}
       result.loserIndex == 0
       result.losingMove == EMPTY_CAST

GIVEN  state = InProgress(moves=[EMPTY_CAST], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOM_HANKS)
THEN   result is RoundOver                           # "Q1" ∉ {}
       result.loserIndex == 0
       result.losingMove == TOM_HANKS
```

Constructing `EMPTY_CAST` must succeed — an empty cast set is legal data
([R13](#r13--invalid-state-and-move-construction-is-rejected)).

---

### Group C — Repeat detection

#### TC-05 — Repeat actor

The submitted move is the correct type for the turn and a valid connection. The repeat is the only
thing that can reject it, so an engine missing [R5](#r5--repeat-detection-is-per-type) fails here
rather than passing incidentally.

```
GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOM_HANKS)
       # Actor after Movie -> type alternation holds
       # "Q1" ∈ CAST_AWAY.castIds -> connection holds
THEN   result is RoundOver
       result.loserIndex == 0
       result.losingMove == TOM_HANKS
       result.chain == [TOM_HANKS, CAST_AWAY]
```

#### TC-06 — Repeat movie

Same isolation as [TC-05](#tc-05--repeat-actor), for the `Movie` branch of
[R5](#r5--repeat-detection-is-per-type). `TWISTER` reappears while still being a legal continuation of
`BILL_PAXTON`.

```
GIVEN  state = InProgress(
           moves=[TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER, BILL_PAXTON],
           currentPlayerIndex=1, playerCount=2)
WHEN   result = playMove(state, TWISTER)
       # Movie after Actor -> type alternation holds
       # "Q3" ∈ TWISTER.castIds -> connection holds
THEN   result is RoundOver
       result.loserIndex == 1
       result.losingMove == TWISTER
       result.chain == [TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER, BILL_PAXTON]
```

#### TC-11 — A cross-type ID collision is not a repeat

Pins [R5](#r5--repeat-detection-is-per-type)'s per-type scoping. This fixture **cannot occur in
production data** — a Wikidata QID identifies exactly one entity, so no real actor and movie share
one. It is a semantic test of the rule, not a data scenario. Keep it: an implementation that scoped
uniqueness by ID alone would pass every other case and fail this one.

```
GIVEN  MOVIE_Q77 = Movie(id="Q77", displayText="Some Movie", castIds={"Q77"})
       ACTOR_Q77 = Actor(id="Q77", displayText="Actor sharing an id with a movie in the chain")
       state = InProgress(moves=[MOVIE_Q77], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, ACTOR_Q77)
THEN   result is InProgress
       # no Actor with id "Q77" in the chain  -> not a repeat
       # "Q77" ∈ MOVIE_Q77.castIds            -> valid connection
       result.moves == [MOVIE_Q77, ACTOR_Q77]
```

#### TC-15 — Identity is the ID; display metadata is ignored

```
GIVEN  RENAMED = Actor(id="Q1", displayText="T. Hanks", imagePath="/other.jpg")
       state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, RENAMED)
       # connection holds ("Q1" ∈ CAST_AWAY.castIds); only identity-by-id can reject it
THEN   result is RoundOver                           # same id as TOM_HANKS -> repeat
       result.loserIndex == 0
       result.losingMove == RENAMED
       result.chain == [TOM_HANKS, CAST_AWAY]
```

#### TC-16 — Repeat detection scans the entire chain

The repeat is at index 0 of a six-move chain, five moves behind the one being checked — not a recent
move. An engine comparing only against the tail passes [TC-05](#tc-05--repeat-actor) and fails here.

```
GIVEN  state = InProgress(moves=LONG_CHAIN, currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOM_HANKS)
       # previous move is APOLLO and "Q1" ∈ APOLLO.castIds -> the connection is valid
THEN   result is RoundOver
       result.loserIndex == 0
       result.losingMove == TOM_HANKS
       result.chain == LONG_CHAIN
```

#### TC-20 — Repeat and connection failure produce identical outcomes

The one case that deliberately stacks failure causes: `CAST_AWAY` here is *both* a repeat and a
same-type-consecutive move. It resolves exactly as either cause alone would. This pins the current
contract — `RoundOver` carries no reason code, so all failure paths are observationally identical. If
a future engine adds a reason field, repeat detection takes priority
([R6](#r6--an-invalid-move-ends-the-round)) and this case gains an assertion.

```
GIVEN  state = InProgress(
           moves=[TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER],
           currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, CAST_AWAY)
       # repeat  ("Q10" already in the chain)                     -> R5
       # AND same-type-consecutive (Movie after TWISTER, a Movie) -> R4
THEN   result is RoundOver
       result.loserIndex == 0
       result.losingMove == CAST_AWAY
       result.chain == [TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER]
```

#### TC-28 — An excluded entity is a repeat even though the chain is clean

Hard mode: the match layer has seeded entities played in earlier rounds. Neither move below appears in
this round's chain, and both are valid connections — the exclusion set is the only thing that can
reject them.

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=0, playerCount=2,
                          excludedMovieIds={"Q10"})
WHEN   result = playMove(state, CAST_AWAY)      # "Q1" ∈ castIds, and Q10 is not in the chain
THEN   result is RoundOver
       result.loserIndex == 0
       result.losingMove == CAST_AWAY
       result.chain == [TOM_HANKS]

GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=1, playerCount=2,
                          excludedActorIds={"Q2"})
WHEN   result = playMove(state, HELEN_HUNT)     # "Q2" ∈ CAST_AWAY.castIds, not in the chain
THEN   result is RoundOver
       result.loserIndex == 1
       result.losingMove == HELEN_HUNT
```

#### TC-29 — Exclusions are per-type

Pins that the exclusion sets carry [R5](#r5--repeat-detection-is-per-type)'s per-type scoping rather
than collapsing into one id set. An implementation storing a single set of excluded ids fails here.

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=0, playerCount=2,
                          excludedActorIds={"Q10"})    # Q10 is CAST_AWAY's id, excluded as an ACTOR
WHEN   result = playMove(state, CAST_AWAY)             # submitting the MOVIE Q10
THEN   result is InProgress                            # the Movie is not barred by an Actor exclusion
       result.moves == [TOM_HANKS, CAST_AWAY]
```

#### TC-30 — Exclusions apply to the opening move

[R1](#r1--the-opening-move-is-not-connection-checked) exempts the opener from the connection and type
checks, not from [R5](#r5--repeat-detection-is-per-type). Without this, hard mode leaks: every round
could open on a banned entity.

```
GIVEN  state = InProgress(moves=[], currentPlayerIndex=0, playerCount=3,
                          excludedActorIds={"Q1"})
WHEN   result = playMove(state, TOM_HANKS)
THEN   result is RoundOver
       result.loserIndex == 0
       result.losingMove == TOM_HANKS
       result.chain == []                              # nothing was ever accepted
```

#### TC-31 — Exclusion sets default to empty

The default mode. Constructing `InProgress` without exclusions must behave exactly as every other case
in this suite assumes, and an entity from a previous round must be playable.

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=0, playerCount=2)
       # constructed with no exclusion arguments at all
WHEN   state.excludedActorIds and state.excludedMovieIds are read
THEN   both are empty

GIVEN  the same state
WHEN   result = playMove(state, CAST_AWAY)
THEN   result is InProgress                            # cross-round reuse is allowed by default
       result.moves == [TOM_HANKS, CAST_AWAY]
```

In a language without default arguments, "constructed without exclusions" means whatever the idiomatic
empty construction is; the requirement is that callers who do not care about the feature never mention
it.

---

### Group D — Terminal transitions

#### TC-07 — Giving up

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=1, playerCount=2)
WHEN   result = forfeit(state)
THEN   result is RoundOver
       result.loserIndex == 1
       result.losingMove is null
       result.chain == [TOM_HANKS]
```

#### TC-24 — Operations are inapplicable to a terminal state

**[static]** In a language whose type system can express this — the operation's parameter type is
`InProgress`, and `RoundState` is a closed sum — the constraint is enforced at compile time and this
case needs no runtime test. Record it as satisfied statically and move on.

Otherwise:

```
GIVEN  terminal = RoundOver(loserIndex=1, chain=[TOM_HANKS], losingMove=null)
WHEN   playMove(terminal, CAST_AWAY)
THEN   raises a programming error
       does NOT return a RoundState             # R15

WHEN   forfeit(terminal)
THEN   raises a programming error
```

---

### Group E — Multiplayer

Multiplayer is a day-one requirement. These cases pin that the engine is N-agnostic: rotation wraps at
any count, and the loser is the player on turn regardless of count or position.

#### TC-12 — Rotation wraps for N > 2

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=2, playerCount=3)
WHEN   result = playMove(state, CAST_AWAY)
THEN   result is InProgress
       result.currentPlayerIndex == 0           # (2 + 1) % 3

GIVEN  the same state
WHEN   result = forfeit(state)
THEN   result is RoundOver
       result.loserIndex == 2                   # the player on turn, not a neighbor
       result.chain == [TOM_HANKS]
```

#### TC-26 — Rotation visits every player once per cycle at N = 4

```
GIVEN  state = InProgress(moves=[], currentPlayerIndex=0, playerCount=4)
WHEN   the first four moves of LONG_CHAIN are played in order, each result the next input
THEN   every intermediate result is InProgress
       currentPlayerIndex after each move is 1, 2, 3, 0 in that order
       final.moves == [TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER]
```

#### TC-27 — The loser is the player on turn, at any N and any index

Pins [R8](#r8--loser-determination) as index-independent. Run it for each listed index; every one must
name the failing player and no one else.

```
GIVEN  playerCount = 5, and for each currentPlayerIndex in [0, 1, 2, 3, 4]:
           state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=<index>, playerCount=5)
WHEN   result = playMove(state, OUTSIDER)       # "Q99" ∉ CAST_AWAY.castIds
THEN   result is RoundOver
       result.loserIndex == <index>
       result.losingMove == OUTSIDER
       result.chain == [TOM_HANKS, CAST_AWAY]
```

The same must hold for `forfeit(state)` at each index, with `losingMove` null.

---

### Group F — Purity

#### TC-18 — The input state is not mutated

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=1, playerCount=2)
       before = deep_copy(state)
WHEN   playMove(state, CAST_AWAY)
       playMove(state, OUTSIDER)
       forfeit(state)
THEN   state == before                          # unchanged after all three calls
```

In a language with immutable-by-default structures this is inherent; assert it anyway — the test
documents the requirement for the next reader.

#### TC-19 — Determinism

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=1, playerCount=2)
WHEN   a = playMove(state, CAST_AWAY)
       b = playMove(state, CAST_AWAY)
THEN   a == b                                   # by value
```

#### S1 — No I/O dependency *(structural, not a test case)*

The engine module must declare no dependency on network, storage, platform, clock, or randomness
APIs. Verify by inspecting the module's dependency declarations, not at runtime. This is a binding
architecture boundary ([AGENTS.md](../AGENTS.md)) — a conforming engine is testable with no mocks,
no fixtures beyond plain data, and no test doubles.

#### S2 — IDs are opaque strings end to end *(structural, not a test case)*

No layer between the graph artifact and the engine may re-map QIDs to integers or any other type.
If a runtime wants a different representation, that adaptation lives in its loader and must not reach
the engine's contract.

#### S3 — The round result names no winner *(structural, not a test case)*

`RoundOver` must expose no winner, runner-up, placement, score, or strike field. Verify by inspecting
the type. This is the [scope boundary](#scope-the-round-engine-not-the-match) made structural: a
winner field would bake one mode's convention into the layer every mode shares, and
[R8](#r8--loser-determination) makes it derivable anyway.

---

### Group G — Input validation

Every case in this group is a **conformance delta**: the Kotlin `:core` prototype does not implement
[R13](#r13--invalid-state-and-move-construction-is-rejected). These are required behavior to build,
not existing behavior to protect.

#### TC-21 — Reject `playerCount < 2`

```
WHEN   InProgress(moves=[], currentPlayerIndex=0, playerCount=1)
THEN   raises a validation error

WHEN   InProgress(moves=[], currentPlayerIndex=0, playerCount=0)
THEN   raises a validation error                # not a division/modulo fault

WHEN   InProgress(moves=[], currentPlayerIndex=0, playerCount=-1)
THEN   raises a validation error
```

No upper bound is imposed. `playerCount` of 12 is as valid as 2.

#### TC-22 — Reject an out-of-range `currentPlayerIndex`

```
WHEN   InProgress(moves=[], currentPlayerIndex=2,  playerCount=2)
THEN   raises a validation error

WHEN   InProgress(moves=[], currentPlayerIndex=-1, playerCount=2)
THEN   raises a validation error

WHEN   InProgress(moves=[], currentPlayerIndex=5,  playerCount=5)
THEN   raises a validation error                # off-by-one at a larger count
```

#### TC-23 — Reject a blank entity ID

```
WHEN   Actor(id="",   displayText="Nameless")
THEN   raises a validation error

WHEN   Actor(id="  ", displayText="Whitespace")
THEN   raises a validation error

WHEN   Movie(id="Q50", displayText="Bad Cast", castIds={"Q1", ""})
THEN   raises a validation error                # blank member of castIds

WHEN   Movie(id="Q40", displayText="No Cast On Record", castIds={})
THEN   succeeds                                 # empty set is legal data
```

---

## Coverage map

Current status of the Kotlin `:core` suite
(`kotlin/core/src/jvmTest/kotlin/me/zwsmith/core/GameEngineTest.kt`). Behavior columns describe the
prototype, not the test.

| TC | Scenario | Rules | Implemented | Tested |
|---|---|---|---|---|
| 01 | Valid movie after actor | R2, R9 | yes | yes |
| 02 | Valid actor after movie | R3, R9 | yes | yes |
| 03 | Movie excludes previous actor | R3, R6 | yes | yes ² |
| 04 | Actor absent from cast | R2, R6 | yes | yes ² |
| 05 | Repeat actor | R5, R6 | yes | partial ¹ |
| 06 | Repeat movie | R5, R6 | yes | no |
| 07 | Giving up | R7, R8 | yes | yes ² |
| 08 | Opening move accepted | R1 | yes | no |
| 09 | Actor after actor | R4, R6 | yes | no |
| 10 | Movie after movie | R4, R6 | yes | no |
| 11 | Cross-type ID collision | R5 | yes | no |
| 12 | Rotation wraps, N > 2 | R8, R9 | partial ² | no |
| 13 | Opening move may be a movie | R1 | yes | no |
| 14 | Connection vs. last move only | R11 | yes | no |
| 15 | Identity is the ID | R12 | yes | no |
| 16 | Repeat scans whole chain | R5 | yes | no |
| 17 | Empty cast connects to nothing | R2, R3 | yes | no |
| 18 | Input not mutated | R10 | yes | no |
| 19 | Determinism | R10 | yes | no |
| 20 | Failure paths indistinguishable | R6 | yes | no |
| 21 | Reject `playerCount < 2` | R13, R15 | **no** | no |
| 22 | Reject out-of-range index | R13, R15 | **no** | no |
| 23 | Reject blank entity ID | R13, R15 | **no** | no |
| 24 | Terminal state inapplicable | R14, R15 | yes (static) | n/a |
| 25 | Full round from an empty chain | R1, R2, R3, R9 | yes | no |
| 26 | Rotation cycle at N = 4 | R9 | yes | no |
| 27 | Loser is the player on turn | R8 | **no** ² | no |
| 28 | Excluded entity is a repeat | R5 | **no** ³ | no |
| 29 | Exclusions are per-type | R5 | **no** ³ | no |
| 30 | Exclusions apply to the opener | R1, R5, R6 | **no** ³ | no |
| 31 | Exclusions default to empty | R5 | n/a ³ | no |
| S1 | No I/O dependency | R10 | yes | structural |
| S2 | IDs opaque end to end | — | **no** — `:core` declares `Int` | structural |
| S3 | Result names no winner | R8 | **no** ² | structural |

¹ `GameEngineTest.kt:72` submits a repeat actor directly after another actor, so the move is rejected
by [R4](#r4--same-type-consecutive-moves-are-always-invalid) whether or not repeat detection exists.
It asserts the right outcome for the wrong reason. [TC-05](#tc-05--repeat-actor) here replaces the
fixture with one that isolates [R5](#r5--repeat-detection-is-per-type).

² The prototype reports `winnerIndex = (currentPlayerIndex - 1 + playerCount) % playerCount` instead
of a loser. At `playerCount == 2` that value coincides with "the player who did not fail," so the
two-player cases pass under either contract; above two players it is wrong, and the contract itself is
wrong at every N ([S3](#s3--the-round-result-names-no-winner-structural-not-a-test-case)).

³ The prototype has no exclusion sets; `isRepeat` scans the chain only. Its behavior is equivalent to
the default mode, so TC-31 is satisfied by construction while TC-28/29/30 are unimplementable against
it.

Four deltas against the prototype: **the winner/loser contract** (R8, S3, and every `RoundOver`
assertion), **cross-round exclusions** (R5's second clause, TC-28–30), **Group G** (R13 construction
validation is absent), and **S2** (`:core` types IDs as `Int`, a TMDB-era leftover —
[AGENTS.md](../AGENTS.md)).

---

## Divergences from source material

Recorded so the reconciliation is auditable rather than silent.

**Winner replaced by loser.** The prototype's `GameOver.winnerIndex` names a winner by stepping back
one position from the failing player. This document specifies `RoundOver.loserIndex` — the failing
player — and no winner at all. The prototype's rule is the two-player convention generalized by
modular arithmetic: at N = 3 it awards the round to the previous player and silently ignores the
third. The round layer has an unambiguous loser and no natural winner, so it reports the former. Any
winner convention is a match-layer overlay ([Scope](#scope-the-round-engine-not-the-match)).

**Cross-round exclusions are new.** Neither the prototype nor the retired spec has any notion of
entities banned from outside the current chain. The sets were added so that a "no repeats for the
whole match" mode has a seam to attach to without the match layer duplicating the engine's failure
path. The default — empty sets, reuse allowed across rounds — is the decided behavior, not a
placeholder.

**Round vs. match layering.** The `movie-actor-chain-game` skill describes a match layer above round
resolution, and sketches penalty-point elimination as one example overlay. That layer is real in this
product — strike-based scoring across repeated rounds, with configurable modes — but it is specified
elsewhere. This document ends at the round result.

**ID type.** `docs/GAME_SPEC_V2.md` (retired in #16) and the current Kotlin suite both use `Int` TMDB
IDs. This document specifies opaque strings, bound to Wikidata QIDs. The data source changed
([ADR 010](DECISIONS.md)); the graph artifact emits QID strings, and AGENTS.md makes the data
authoritative over the stale `:core` signature.

**TC-11's fixtures.** The retired spec's TC-11 restated itself three times before landing on a usable
form. This document uses the final `state3` shape, and adds the note that QIDs make the collision
impossible in real data — which is why the case survives as a semantics test rather than being cut.

**Repeat-case fixtures are not the Kotlin suite's.** The existing repeat test submits the repeated
actor immediately after another actor, so [R4](#r4--same-type-consecutive-moves-are-always-invalid)
rejects it before [R5](#r5--repeat-detection-is-per-type) is ever consulted — an engine with repeat
detection deleted still passes. [TC-05](#tc-05--repeat-actor), [TC-06](#tc-06--repeat-movie), and
[TC-15](#tc-15--identity-is-the-id-display-metadata-is-ignored) use fixtures where the move is a legal
continuation in every other respect, so only the repeat rule can reject it.

**Defensive validation.** [R13](#r13--invalid-state-and-move-construction-is-rejected)/[R15](#r15--malformed-input-is-an-error-never-a-round-outcome)
are new requirements, not a record of existing behavior — see Group G.

---

## Open questions

Unresolved. Each needs a decision before the area it touches is built. None of them block the round
engine — they are match-layer and contract questions the round engine's output feeds.

**Failure reason codes — the highest-priority question here.** `RoundOver` records *that* a move lost,
not *why* — a repeat, a bad connection, a wrong type, and a give-up are indistinguishable to the
caller. This matters more now that a match layer consumes round results: a mode that charges a
different penalty for giving up than for a wrong answer, or a UI that says "you already used that,"
needs the distinction. Adding it changes the `RoundOver` contract and gives
[TC-20](#tc-20--repeat-and-connection-failure-produce-identical-outcomes) real assertions.

[ADR 018](DECISIONS.md) raised this question's priority. With a per-turn deadline now the *only* time
mechanism in the product, **"ran out of time" and "gave up" are the same `RoundOver`** — and they are
the pair most likely to warrant different treatment, since a correspondence player who lets a
three-day deadline lapse has not made the same choice as one who taps "give up." Two of the other open
questions below also resolve into this contract rather than into new operations.

**Whether the match layer needs the round's opening player index.** Move attribution is derivable from
it ([Engine boundary](#engine-boundary)) and the match layer holds it — but nothing yet specifies that
the match layer records it, and without it a persisted round result cannot be replayed with
attribution.

**Deadline expiry ownership.** [ADR 012](DECISIONS.md) puts time controls in scope;
[ADR 018](DECISIONS.md) **simplified this question** by dropping the running chess clock — there is now
one time model, not two. A turn carries a `deadline_at` timestamp, and expiry is adjudicated by the
session layer (lazily on next read, or by a sweeper), which resolves it to a `forfeit` call.

What remains open is narrower than before: the engine stays timeless ([R10](#r10--the-engine-is-pure)),
so a lapsed deadline and a deliberate give-up produce identical `RoundOver` values. That is now purely
a **reason-code** question (above), not a clock-architecture one. Note also that the adjudicator is not
a player, which is one of the three writers the session layer's optimistic concurrency exists to
serialize (`AGENTS.md`, [ADR 018](DECISIONS.md) §4).

**An exhausted frontier is indistinguishable from a player's failure.** Nothing in this spec expresses
"the player on turn had *no* legal move." [R6](#r6--an-invalid-move-ends-the-round) and
[R8](#r8--loser-determination) both assume the player on turn is at fault; a player who arrives at an
entity whose every graph neighbour is already in the chain (or excluded) is named the loser exactly as
if they had guessed wrong.

**This is not by itself a defect.** Steering the chain toward an entity the next player cannot continue
from is a legitimate winning move — knowing that an actor has exactly one credit is precisely the
knowledge this game tests, and driving play into obscure territory is strategy, not abuse. Obscurity is
the skill gradient; the design should not try to flatten it.

The open question is narrower: **whether a round-ending move is cheap or earned.** A kill reachable
only by first steering into a little-known film is earned. A kill available to anyone who names a
household-name film and then recalls one bit-part name from it is cheap, and cheap kills compress the
game. A further distinction matters for whether this is a data problem at all: an actor with exactly
one credit *in reality* is legitimate content, whereas an actor with one credit only because
[the cast cap](../etl/AGENTS.md) truncated the others is a build artifact — and the two are
indistinguishable from the artifact alone.

The engine cannot fully detect this, and the asymmetry is in the [data model](#data-model): `Movie`
carries `castIds`, so an exhausted frontier *is* computable when the chain head is a movie; `Actor`
carries no filmography, so the engine is structurally blind to it when the head is an actor. Closing
that by adding a `filmIds` set to `Actor` would widen the validation contract and the per-move payload.

The cheaper placement is the session layer, which holds the graph and can compute the legal-move set in
either direction in O(degree) — and can do so *before* the round ends rather than after. What is
genuinely undecided is the policy (does an exhausted frontier end the round without a strike? is the
*previous* move rejected as a dead end?) and whether `RoundOver` needs to express the distinction at
all, which folds back into reason codes. **How common this is in the shipped graph is unmeasured** —
see the actor-degree probe; the answer should inform the policy rather than the reverse.

**Chain length limits.** Nothing bounds chain growth. With correspondence the only mode
([ADR 018](DECISIONS.md)), a round spanning weeks is the normal case rather than an edge case, so an
unbounded `moves` list is a persistence and payload concern before it is an engine one.

---

## Related documents

| Document | Relationship |
|---|---|
| [AGENTS.md](../AGENTS.md) | Architecture boundaries; which of these rules are binding vs. provisional |
| [docs/DECISIONS.md](DECISIONS.md) | ADRs 008–018 — the reasoning behind the data source, deployment, and mode decisions. [ADR 018](DECISIONS.md) is the one that touches this spec: it drops the running chess clock, leaving a single deadline model |
| `movie-actor-chain-game` skill | Domain rules and vocabulary; implementation-agnostic, leaves repeats/opener/"appeared in" open — answered here and in AGENTS.md |
| [etl/AGENTS.md](../etl/AGENTS.md) | How `castIds` is produced; `cast_cap` and `min_cast` define what "appeared in" means in practice |
| [issue #17](https://github.com/zws33/bacons_law/issues/17) | The coverage gap this document supersedes |

**Not yet written:** the match-layer spec — strike accounting, mode configuration, elimination and
match-end conditions, standings. This document's [Scope](#scope-the-round-engine-not-the-match)
section defines the seam it must attach to.
