# Bacon's Law — Round Engine Conformance Spec

**Status:** Authoritative for round-engine behavior. Language- and framework-agnostic.

This document defines the minimum behavior any Bacon's Law **round engine** must exhibit, expressed as
rules plus a numbered conformance suite. It exists so that engine behavior survives a change of
language, framework, or module layout — the application stack is provisional
([AGENTS.md](../AGENTS.md)), the rules below are not.

---

## Scope: the round engine, not the match

The system has two layers. This document specifies **only the lower one**.

**The round engine** builds one chain. It accepts an opening move, rotates turns among N players,
validates each submission against the previous move, and — when a player submits a move that does not
connect, or gives up, or lets a deadline lapse — ends the round and reports **who failed**. That is the
whole of its job.

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

### Where the seam falls

A rule belongs to the round engine when it is **constitutive** — when without it the thing being built
is not a chain. It belongs to the match layer when it is **regulative** — when the connection is real
and the rule merely forbids using it.

Type alternation is constitutive: a movie following a movie is not a chain, whatever the IDs.
What a failure *costs* is regulative: the same broken chain can be worth one strike, elimination, or
nothing, and none of those change how the turn was evaluated.

**The test is not purely mechanical, and [R5](#r5--availability-repeats-and-exclusions) is the worked
example.** In-round repeat prohibition *looks* regulative — Leonardo DiCaprio was in *Shutter Island*
whether or not either has already appeared, so the connection is factually real and forbidding it
looks like policy. It is nonetheless constitutive, because it is the only thing that makes a round
finite ([R17](#r17--every-round-terminates)). Without it a chain can cycle between two entities
forever. A rule that the game cannot terminate without is not policy, however arbitrary it looks in
isolation.

Cross-round exclusions do not carry that justification and remain regulative — hence R5's two clauses
have different modalities.

---

## How to use this document

**To implement an engine:** satisfy every rule in [Rules](#rules). The
[Engine boundary](#engine-boundary) table lists what you must *not* enforce here.

**To generate a test suite:** each `TC-nn` in [Conformance suite](#conformance-suite) becomes exactly
one test. Translate the fixtures once into a shared fixture module, then translate each case's GIVEN/WHEN/THEN literally. Keep the `TC-nn` identifier in the test name so coverage stays traceable to this document.

**To evaluate a proposed design:** a design that cannot satisfy these cases without an I/O call, a network hop, or a per-turn external lookup violates the spec

**What this document is not:** it does not specify transport, persistence, UI, identity, time controls, scoring, or match structure. It specifies one round, played by pure state transitions.

---

## Vocabulary

The document uses the `movie-actor-chain-game` skill's terms. The Kotlin prototype's names are mappedhere only so the old code is readable; prefer the **Spec term** column in new code.

| Spec term     | `movie-actor-chain-game` skill |
| ------------- | ------------------------------ |
| Move          | Entity                         |
| Move type     | Entity Type                    |
| Chain         | The round's sequence of turns  |
| Previous move | Prompt Entity                  |
| Required type | Required Type                  |
| Round         | Round                          |
| Round over    | Round end                      |
| Loser         | The failing player             |

**One round is one chain.** A match is a series of rounds; that layer exists but is specified
elsewhere.

| Term            | Meaning                                                                                                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Unconnected** | A submission of the correct type, available, that has no edge to the previous move. Ends the round with `reason == Unconnected` ([R6](#r6--an-unconnected-move-ends-the-round))  |
| **Available**   | Not already played in this round and not in the match layer's exclusion set for its type. An unavailable submission ends the round ([R5](#r5--availability-repeats-and-exclusions)) |

**Graph membership defines validity, not real-world truth.** An edge the artifact does not carry is not a legal move, however true it is off-graph. The engine tests `castIds` and nothing else ([R12](#r12--identity-is-the-id-alone)), and `castIds` comes from a graph built offline with a cast
cap, so a real but obscure cast member is absent from the graph and is therefore not a valid move. This is a property of the data the engine is handed, not a rule the engine applies — it is stated here because it is the one place a reader is likely to mistake a legitimate lost round for a bug. The cap is a dial (`cast_cap`, `min_cast` — etl/AGENTS.md), and expect the argument to recur in playtests.

---

## Data model

Notation is pseudo-code. `?` marks an optional field. 

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

`castIds` is the only field that participates in validation. Everything else is metadata carried for the presentation layer — see [R12](#r12--identity-is-the-id-alone).

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
    losingMove:   Move?                # the failing move on Unconnected or Repeat; null on forfeit
    reason:       RoundEndReason

RoundEndReason = Unconnected | Repeat | GaveUp | DeadlineLapsed
ForfeitReason  = GaveUp | DeadlineLapsed       # the RoundEndReason values forfeit may produce

RoundState = InProgress | RoundOver            # what a caller persists, and every playMove outcome
```

**`ForfeitReason` is a proper subset of `RoundEndReason`.** `Unconnected` is unreachable through `forfeit`, and a type system that can express the subset should — passing `Unconnected` to `forfeit` is a caller error, not a round outcome.

**`RoundOver` carries no winner.** See [R8](#r8--loser-determination) and [S3](#s3--the-round-result-names-no-winner-structural-not-a-test-case).

**Why `reason` exists.** The match layer charges penalties, and the penalties differ. A correspondence player who lets a three-day deadline lapse has not made the same choice as one who taps "give up," and both differ from one who guessed wrong — yet all produce `RoundOver` with the same loser. `losingMove != null` separates a `playMove` loss from a forfeit but not `Unconnected` from `Repeat`; making the match layer's penalty table pattern-match on a field's presence would collapse reasons it must charge apart, so the reason is explicit for all four.

**The exclusion sets are how a match forbids reuse across rounds.** Both default to empty, which is the default mode: a new round starts with every entity available again. A mode that forbids reuse for the whole match seeds them with everything played in earlier rounds. The engine does not know which mode is in play — it reads two sets and applies [R5](#r5--availability-repeats-and-exclusions). Populating them is the match layer's job; see [Engine boundary](#engine-boundary).

**Player indices are positions in a roster fixed for the round.** The engine never adds or removes players mid-round, so an index is stable from the opening move to the round's end. A match layer that
drops an eliminated player does so *between* rounds, by starting the next round with a smaller `playerCount`.

## Operations

```
playMove(state: InProgress, move: Move)            -> RoundState    # InProgress or RoundOver
forfeit(state: InProgress, reason: ForfeitReason)  -> RoundOver
```

Both are pure functions of their arguments. Neither performs I/O. Neither mutates its input. `forfeit` means "the player on turn cannot continue this round" — an explicit give-up, or a deadline the session layer has adjudicated as lapsed. It concedes **the round, not the match**; a player quitting the match outright is a match-layer event that happens to end the current round this way.

**`forfeit` takes the reason because the engine cannot infer it.** [R10](#r10--the-engine-is-pure)
denies the engine a clock, so it cannot tell a give-up from a lapse; the session layer knows which one it is adjudicating and says so. This is the one piece of caller intent the engine records without verifying.

### Move outcomes

`playMove` either raises an error or returns exactly one of two outcomes. They differ in what the
caller persists and in whether the player on turn keeps the turn. The error row is listed for
completeness — it is raised, never returned
([R15](#r15--malformed-input-is-an-error-never-a-round-outcome)).

| Outcome        | Cause                                                                                                                                                           | Turn advances | Caller persists    | Round ends                                                                              |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------- | ------------------ | --------------------------------------------------------------------------------------- |
| **Error**      | [R13](#r13--invalid-state-and-move-construction-is-rejected)/[R14](#r14--operations-are-inapplicable-to-terminal-states) violations — blank ID, terminal state, wrong-type move | —             | nothing            | no — programming error ([R15](#r15--malformed-input-is-an-error-never-a-round-outcome)) |
| **InProgress** | Accepted                                                                                                                                                          | yes           | the new state      | no                                                                                      |
| **RoundOver**  | Unavailable ([R5](#r5--availability-repeats-and-exclusions)), unconnected ([R6](#r6--an-unconnected-move-ends-the-round)), or `forfeit` ([R7](#r7--forfeit-ends-the-round)) | —             | the terminal state | yes                                                                                     |

**Evaluation order is normative: type, then availability, then connection**, and it fixes the
round-end reason. A wrong-type move is validated out above the engine — statically, or at the
untyped-input boundary — and reaching `playMove` is a programming error
([R4](#r4--consecutive-moves-must-alternate-type), [R15](#r15--malformed-input-is-an-error-never-a-round-outcome)).
Availability is checked next: an unavailable move ends the round with `reason == Repeat`. Connection is
checked last: an unconnected move ends the round with `reason == Unconnected`. A move that is both
unavailable and unconnected resolves to `Repeat`, because availability precedes connection.

The reason is not cosmetic: it is what the client shows the player and what the match layer charges
against. "You already used that" and "that doesn't connect" send the player looking for different
mistakes, so the order that decides between them is normative, not an implementation detail.

---

## Rules

### R1 — The opening move is not connection-checked

When `moves` is empty, `playMove` performs no connection check and no type check: an opening move may
be either an Actor or a Movie. In the default mode every entity is a legal opener; the availability
check still runs and is what makes that qualified rather than absolute (below).

*Rationale:* there is no predecessor to connect to, and no earlier move to alternate from.
"The first move must be an Actor" is not a rule of this game; if some mode wants it, that is a
caller-layer constraint — see [Engine boundary](#engine-boundary).

**[R5](#r5--availability-repeats-and-exclusions) still applies.** On an empty chain with empty exclusion sets
it is vacuous — nothing has been played, so nothing can be a repeat — which is why the opener is
accepted unconditionally in the default mode. It is *not* vacuous when the match layer has seeded
exclusions: an excluded entity cannot open a round — submitting one ends the round
(`RoundOver`, `reason == Repeat`), see [TC-30](#tc-30--exclusions-apply-to-the-opening-move). R1
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

### R4 — Consecutive moves must alternate type

`Actor` after `Actor`, or `Movie` after `Movie`, is not a chain regardless of IDs. The chain strictly
alternates.

A wrong-type submission is **not** a `playMove` outcome. The required type is fully determined by the
chain, so type correctness is guaranteed before the move reaches the engine — either statically, or by
the boundary that deserializes untyped input, which surfaces a wrong type there as an input error. A
wrong-type `Move` that nonetheless reaches `playMove` is a programming error
([R15](#r15--malformed-input-is-an-error-never-a-round-outcome)), never a round outcome; charging a
loss for it would penalize the player for their client's defect.

**This rule may be enforced by the type system instead of at runtime.** An engine whose `InProgress`
is split by required type — so that `playMove` on a state awaiting an Actor accepts only an `Actor` —
makes a wrong-type submission unrepresentable, and needs no runtime branch for it. It must still
validate type at the boundary where untyped input becomes a `Move`; static enforcement relocates the
check, it does not remove it. The same MAY/MUST split as
[R14](#r14--operations-are-inapplicable-to-terminal-states).

### R5 — Availability: repeats and exclusions

A move is **available** iff no move **of the same type** with the same `id` already appears anywhere in
the chain, and its `id` does not appear in the exclusion set for its type:

```text
isAvailable(move, state) =
    match move:
        Actor -> move.id ∉ state.excludedActorIds
                 and none(m.id == move.id for m in state.moves where m is Actor)
        Movie -> move.id ∉ state.excludedMovieIds
                 and none(m.id == move.id for m in state.moves where m is Movie)
```

An unavailable move ends the round: `RoundOver` with `reason == Repeat`
([R16](#r16--an-unavailable-move-ends-the-round)).

Uniqueness is scoped within a type, for both the chain and the exclusion sets. An Actor and a Movie
sharing an `id` do not collide, and an id in `excludedMovieIds` does not bar an Actor with that id.

**The two clauses have different modalities. They share an implementation, not a justification.**

**Clause 1 — in-round repeats: MUST.** Within a round the same entity may never appear twice, in every
mode, with no way to turn it off. This is not a difficulty setting: it is the sole guarantee that a
round is finite ([R17](#r17--every-round-terminates)). An engine that makes it configurable admits
non-terminating rounds.

**Clause 2 — exclusion sets: MAY, default empty.** A fresh round makes every entity from earlier rounds
available again. A mode that forbids reuse across a whole match seeds the sets; the engine's check is
unchanged either way and it does not know which mode is in play. Cross-round reuse threatens no
termination guarantee — clause 1 still forces each round's chain outward — so this clause is genuine
match-layer policy and is chosen in game settings before play.

Unlike [R4](#r4--consecutive-moves-must-alternate-type), **this rule cannot be enforced by a type
system.** Availability is a predicate over a runtime set; no type discipline available in a practical
implementation language can express "this id is not in that collection." It is always a runtime check.

### R6 — An unconnected move ends the round

The round ends immediately when a move of the correct type ([R4](#r4--consecutive-moves-must-alternate-type))
that is available ([R5](#r5--availability-repeats-and-exclusions)) is nonetheless not a valid connection
to the previous move ([R2](#r2--actor-after-movie)/[R3](#r3--movie-after-actor)). `RoundOver.reason` is
`Unconnected`.

**`playMove` ends a round two ways, distinguished by `reason`.** An unavailable move ends it with
`reason == Repeat` ([R5](#r5--availability-repeats-and-exclusions), [R16](#r16--an-unavailable-move-ends-the-round));
an unconnected move ends it with `reason == Unconnected`. A wrong-type or malformed input is an error,
never a round outcome ([R15](#r15--malformed-input-is-an-error-never-a-round-outcome)).

Note the asymmetry, which follows from [R1](#r1--the-opening-move-is-not-connection-checked): the
connection check requires a predecessor and so is skipped on an empty chain, while the availability
check always runs. **An opening move can therefore end the round by being unavailable, but never by
failing to connect** — in a mode that seeded exclusions ([TC-30](#tc-30--exclusions-apply-to-the-opening-move)).

`RoundOver.losingMove` is the unconnected move. `RoundOver.chain` holds the moves accepted **before**
it — the losing move is never appended.

### R7 — Forfeit ends the round

`forfeit` ends the round immediately. `RoundOver.losingMove` is null, `RoundOver.chain` is the chain
unchanged, and `RoundOver.reason` is the `ForfeitReason` the caller supplied — `GaveUp` or
`DeadlineLapsed`.

The engine does not distinguish the two itself and must not try: [R10](#r10--the-engine-is-pure) leaves
it no clock. It records what the session layer tells it.

### R8 — Loser determination

```text
loserIndex = currentPlayerIndex
```

The player on turn is the player who failed, whether by an unavailable move
([R5](#r5--availability-repeats-and-exclusions)), an unconnected move
([R6](#r6--an-unconnected-move-ends-the-round)), or by forfeit ([R7](#r7--forfeit-ends-the-round)).
This holds at every `playerCount` — there is no arithmetic and no special case for N > 2.

**The engine names no winner and no runner-up, and imposes no ordering on the players who did not
fail.** A mode that wants "the player who made the last valid move wins" can compute
`(loserIndex - 1 + playerCount) % playerCount` at the match layer; that it is derivable from the round
result is precisely why it does not belong in the round result.

### R9 — Player rotation

After an accepted move:

```text
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

Rejection happens **at construction**, not deferred to `playMove`. An invalid state must not be representable. `Movie.castIds` being an *empty set* is valid — it is legal data, not malformation. Such a movie simply connects to no actor in either direction. (The ETL's `min_cast` floor means it should not occur in practice; the engine must not depend on that.)

### R14 — Operations are inapplicable to terminal states

`playMove` and `forfeit` accept only `InProgress`. In a language whose type system can express this,
the signature must enforce it statically and no runtime check is required. Otherwise, invoking either
on a `RoundOver` must raise a programming error.

### R15 — Malformed input is an error, never a round outcome

Violations of [R13](#r13--invalid-state-and-move-construction-is-rejected) and
[R14](#r14--operations-are-inapplicable-to-terminal-states) must surface as errors distinguishable
from normal results. They must never be reported as a `RoundState` — not an `InProgress`, and not a
`RoundOver`.

*Rationale:* a malformed input silently resolving to a loss would end real rounds incorrectly and
charge a strike to a player who did nothing wrong. A programming error must surface as an error, so the
defect is not converted into a routine result and lost.

### R16 — An unavailable move ends the round

An unavailable move ([R5](#r5--availability-repeats-and-exclusions)) — an in-round repeat, or an entity
in a match exclusion set — ends the round. `RoundOver.reason` is `Repeat`, `RoundOver.losingMove` is
the unavailable move, and `RoundOver.chain` excludes it, mirroring
[R6](#r6--an-unconnected-move-ends-the-round). The loser is the player on turn
([R8](#r8--loser-determination)).

### R17 — Every round terminates

**The chain is finite — the engine guarantees this.** Every accepted move permanently consumes one
entity of its type from a finite corpus ([R5](#r5--availability-repeats-and-exclusions), clause 1), and
[R4](#r4--consecutive-moves-must-alternate-type) forces the types to alternate, so the set of
available entities strictly decreases with each accepted move and the chain cannot exceed
`2 × min(|actors|, |movies|) + 1`. Every submission that is not accepted — unavailable, unconnected, or
a forfeit — ends the round, so no submission can prolong a round without shortening the corpus.

Without clause 1 that bound does not exist: a chain can cycle between the same two entities forever.
This is the whole reason clause 1 is not configurable, and it is why "repeats are on" is a property of
the engine rather than a setting a mode may choose.

**A turn on which no move arrives is bounded by the deadline — the session layer guarantees this.** The
engine has no clock ([R10](#r10--the-engine-is-pure)); a turn on which the player never submits is
ended by the session layer resolving the deadline to `forfeit(state, DeadlineLapsed)`.

*The bound is a proof, not a limit.* Roughly 95,000 moves is not a useful cap on a real round — see
[Chain length limits](#open-questions), which this does not settle.

---

## Engine boundary

Required by the game, enforced elsewhere. An engine that enforces these is over-scoped.

| Constraint                                                                                             | Enforced by                                                                                                                                                                                  |
| ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| What a round loss costs — strikes, elimination, match end                                              | Match layer                                                                                                                                                                                  |
| Strike limits, standings, ranking across an ongoing series                                             | Match layer                                                                                                                                                                                  |
| Game-mode configuration, fixed before the round starts                                                 | Match layer                                                                                                                                                                                  |
| Naming a winner, if the mode defines one                                                               | Match layer ([R8](#r8--loser-determination))                                                                                                                                                 |
| Who opens the next round, and with which roster                                                        | Match layer; it passes the next round a `playerCount`                                                                                                                                        |
| Whether entities reuse across rounds — and seeding `excludedActorIds` / `excludedMovieIds` accordingly | Match layer; the engine applies the sets it is given ([R5](#r5--availability-repeats-and-exclusions))                                                                                        |
| Requiring the opening move to be an Actor, if a mode wants it                                          | Caller (session / UI layer)                                                                                                                                                                  |
| The player is offered the correct entity type each turn                                                | Caller filters its typeahead to the required type; type is validated statically or at the input boundary ([R4](#r4--consecutive-moves-must-alternate-type)), and a wrong type reaching `playMove` is a programming error ([R15](#r15--malformed-input-is-an-error-never-a-round-outcome)) |
| The player is not offered an entity already played, or excluded                                        | Caller filters its typeahead against the chain and the exclusion sets; [R5](#r5--availability-repeats-and-exclusions) is the backstop — an unavailable entity reaching `playMove` ends the round ([R16](#r16--an-unavailable-move-ends-the-round))                                          |
| `castIds` is accurate and complete                                                                     | Caller populates from the graph before constructing the move                                                                                                                                 |
| Name resolution, typos, disambiguation                                                                 | Caller, before a `Move` exists                                                                                                                                                               |
| **Bounding a turn on which no move arrives, so the round terminates**                                  | **Session layer, via the deadline. The engine bounds the chain; a silent turn is ended by the deadline — [R17](#r17--every-round-terminates)**                                               |
| **Deciding whether a forfeit is `GaveUp` or `DeadlineLapsed`**                                         | **Session layer; it passes the reason to `forfeit`. The engine has no clock ([R10](#r10--the-engine-is-pure))**                                                                              |
| Mapping a deadline expiry or an abandonment onto a round result                                        | Session layer; it calls `forfeit`                                                                                                                                                            |
| Detecting that the player on turn has no legal move at all                                             | Session layer; it holds the graph. The engine cannot see it when the chain head is an Actor — see [Open questions](#open-questions)                                                          |
| Persistence, transport, presence                                                                       | Session layer                                                                                                                                                                                |

---

## Conformance suite

**Fixture identifiers are synthetic.** The QIDs below are QID-*shaped* placeholders, not real Wikidata identifiers, and the display names are for readability only ([R12](#r12--identity-is-the-id-alone)).
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
([R6](#r6--an-unconnected-move-ends-the-round)) and that `reason` is the expected `RoundEndReason`.

**Two properties hold across the suite; preserve both when translating.**

*Every GIVEN chain is legally reachable.* Each fixture chain could have been produced by playing its
moves in order from an empty chain — every adjacent pair alternates type and connects. A case that
asserts behavior from an unreachable chain proves nothing about a real round. `currentPlayerIndex` is
independent: the engine keeps no record of who played which move, so any in-range index is a valid
state to test, and several cases set one that does not match the chain's length.

*Each case isolates one rule.* Where a move could fail more than one check, the fixtures are chosen so
exactly one applies — a repeat case is a valid connection of the correct type, so an engine with no
availability check fails it rather than passing by accident.
[TC-20](#tc-20--type-is-validated-before-availability) and
[TC-33](#tc-33--availability-is-evaluated-before-connection) are the two exceptions; stacking causes
is precisely the behavior they exist to pin. Do not "simplify" a fixture during translation; the
specific IDs are load-bearing.

**Cases marked [static-eligible]** may be satisfied by the type system rather than a runtime test, per
[R4](#r4--consecutive-moves-must-alternate-type) — an engine that splits `InProgress` by required
type cannot express the WHEN clause. Record such a case as satisfied statically, and test the
wrong-type input error at the boundary that deserializes untyped input instead.

---

### Group A — Chain construction and turn advance

#### TC-01 — Valid movie after actor

```text
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=1, playerCount=2)
WHEN   result = playMove(state, CAST_AWAY)          # "Q1" ∈ {"Q1","Q2"}
THEN   result is InProgress
       result.moves == [TOM_HANKS, CAST_AWAY]
       result.currentPlayerIndex == 0
```

#### TC-02 — Valid actor after movie

```text
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

Every case in this group ends the round. A move reaching the connection check has already passed the
type and availability checks ([Move outcomes](#move-outcomes)), so `Unconnected` is the only outcome
left.

#### TC-03 — Movie whose cast excludes the previous actor

```
GIVEN  state = InProgress(moves=[HELEN_HUNT], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOY_STORY)          # "Q2" ∉ {"Q1"}
THEN   result is RoundOver
       result.loserIndex == 0
       result.losingMove == TOY_STORY
       result.chain == [HELEN_HUNT]
       result.reason == Unconnected
```

#### TC-04 — Actor absent from the previous movie's cast

```
GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, OUTSIDER)           # "Q99" ∉ {"Q1","Q2"}
THEN   result is RoundOver
       result.loserIndex == 0
       result.losingMove == OUTSIDER
       result.chain == [TOM_HANKS, CAST_AWAY]
       result.reason == Unconnected
```

#### TC-14 — Connection is evaluated against the immediately preceding move only

`EARLY_ONLY` is in the cast of `UNRELATED`, which sits earlier in the chain, but not in the cast of
`CAST_AWAY`, which is last. It is not a repeat, so the only thing that can end the round on it is
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
       result.reason == Unconnected
```

#### TC-17 — A movie with an empty cast connects to nothing

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, EMPTY_CAST)
THEN   result is RoundOver                           # "Q1" ∉ {}
       result.loserIndex == 0
       result.losingMove == EMPTY_CAST
       result.reason == Unconnected

GIVEN  state = InProgress(moves=[EMPTY_CAST], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOM_HANKS)
THEN   result is RoundOver                           # "Q1" ∉ {}
       result.loserIndex == 0
       result.losingMove == TOM_HANKS
       result.reason == Unconnected
```

Constructing `EMPTY_CAST` must succeed — an empty cast set is legal data
([R13](#r13--invalid-state-and-move-construction-is-rejected)).

---

### Group C — Availability and type

**Availability cases in this group end the round; type cases are validated above the engine.** An
unavailable submission ends the round with `reason == Repeat`
([R5](#r5--availability-repeats-and-exclusions), [R16](#r16--an-unavailable-move-ends-the-round)); a
wrong-type submission is statically prevented or a boundary input error
([R4](#r4--consecutive-moves-must-alternate-type)), never a `playMove` outcome.

#### TC-09 — Actor after actor

**[static-eligible]** Wrong type is not a `playMove` outcome
([R4](#r4--consecutive-moves-must-alternate-type)).

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=1, playerCount=2)
WHEN   an Actor is submitted where a Movie is required
THEN   under static enforcement the submission is unrepresentable — recorded as satisfied statically
       otherwise the untyped-input boundary raises a wrong-type input error, before playMove
       a wrong-type Move reaching playMove is a programming error (R15), never a round outcome
```

#### TC-10 — Movie after movie

**[static-eligible]** Wrong type on type grounds ([R4](#r4--consecutive-moves-must-alternate-type))
even though `TOY_STORY.castIds` contains `"Q1"`. An implementation that checked cast membership without
checking type would wrongly *accept* it.

```
GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=0, playerCount=2)
WHEN   a Movie is submitted where an Actor is required
THEN   under static enforcement the submission is unrepresentable — recorded as satisfied statically
       otherwise the untyped-input boundary raises a wrong-type input error, before playMove
       a wrong-type Move reaching playMove is a programming error (R15), never a round outcome
```

#### TC-05 — Repeat actor

The submitted move is the correct type for the turn and a valid connection. Availability is the only
thing that can end the round here, so an engine missing [R5](#r5--availability-repeats-and-exclusions)
fails this case rather than passing incidentally.

```
GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOM_HANKS)
       # Actor after Movie -> type alternation holds
       # "Q1" ∈ CAST_AWAY.castIds -> connection holds
THEN   result is RoundOver
       result.reason == Repeat
       result.loserIndex == 0
       result.losingMove == TOM_HANKS
       result.chain == [TOM_HANKS, CAST_AWAY]
```

#### TC-06 — Repeat movie

Same isolation as [TC-05](#tc-05--repeat-actor), for the `Movie` branch of
[R5](#r5--availability-repeats-and-exclusions). `TWISTER` reappears while still being a legal continuation of
`BILL_PAXTON`.

```
GIVEN  state = InProgress(
           moves=[TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER, BILL_PAXTON],
           currentPlayerIndex=1, playerCount=2)
WHEN   result = playMove(state, TWISTER)
       # Movie after Actor -> type alternation holds
       # "Q3" ∈ TWISTER.castIds -> connection holds
THEN   result is RoundOver
       result.reason == Repeat
       result.loserIndex == 1
       result.losingMove == TWISTER
       result.chain == [TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER, BILL_PAXTON]
```

#### TC-11 — A cross-type ID collision is not a repeat

Pins [R5](#r5--availability-repeats-and-exclusions)'s per-type scoping. This fixture **cannot occur in
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
       # connection holds ("Q1" ∈ CAST_AWAY.castIds); only identity-by-id can end the round on it
THEN   result is RoundOver                           # same id as TOM_HANKS -> unavailable
       result.reason == Repeat
       result.loserIndex == 0
       result.losingMove == RENAMED
       result.chain == [TOM_HANKS, CAST_AWAY]
```

#### TC-16 — Availability scans the entire chain

The repeat is at index 0 of a six-move chain, five moves behind the one being checked — not a recent
move. An engine comparing only against the tail passes [TC-05](#tc-05--repeat-actor) and fails here.

```
GIVEN  state = InProgress(moves=LONG_CHAIN, currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOM_HANKS)
       # previous move is APOLLO and "Q1" ∈ APOLLO.castIds -> the connection is valid
THEN   result is RoundOver
       result.reason == Repeat
       result.loserIndex == 0
       result.losingMove == TOM_HANKS
       result.chain == LONG_CHAIN
```

#### TC-20 — Type is validated before availability

**[static-eligible]** The first of two cases that deliberately stack causes. `CAST_AWAY` here is *both*
unavailable and the wrong type. Type is validated above the engine, ahead of the availability check, so
the submission surfaces as a wrong-type input error and never reaches the availability check that would
have called it a repeat.

The distinction is not cosmetic: it is what the client shows the player, and "you already used that"
for a submission that was actually the wrong type sends them looking for the wrong mistake.

```
GIVEN  state = InProgress(
           moves=[TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER],
           currentPlayerIndex=0, playerCount=2)
WHEN   CAST_AWAY is submitted where an Actor is required
       # same-type-consecutive (Movie after TWISTER, a Movie) -> R4, wrong type
       # AND unavailable ("Q10" already in the chain)         -> R5
THEN   the untyped-input boundary raises a wrong-type input error   # type checked before availability
       availability is never consulted, so the round does not end as a Repeat
```

Under static enforcement this case is unreachable — the WHEN clause will not compile — and the
precedence it pins is enforced by construction. Record it as satisfied statically.

#### TC-33 — Availability is evaluated before connection

The second stacked case, and the one that decides which `reason` the loser is charged. `TWISTER` is the
correct type for the turn, is **already in the chain**, and **would not have connected** either. Both
causes end the round; availability is evaluated before connection, so the reason is `Repeat`, not
`Unconnected`.

An engine that evaluated the connection first would report `Unconnected` here — sending the player
looking for a connection mistake when the real fault was a repeat. This is the case that makes the
evaluation order in [Move outcomes](#move-outcomes) observable.

```
GIVEN  state = InProgress(
           moves=[HELEN_HUNT, TWISTER, BILL_PAXTON, APOLLO, TOM_HANKS],
           currentPlayerIndex=1, playerCount=2)
       # Q2 -> {Q2,Q3} -> Q3 -> {Q1,Q3} -> Q1 : valid at every step

WHEN   result = playMove(state, TWISTER)
       # Movie after Actor                    -> R4 passes, type is correct
       # "Q50" already in the chain           -> R5 fails
       # "Q1" ∉ TWISTER.castIds {"Q2","Q3"}   -> R6 would also have failed

THEN   result is RoundOver                    # availability precedes connection
       result.reason == Repeat                # NOT Unconnected
       result.loserIndex == 1
       result.losingMove == TWISTER
       result.chain == [HELEN_HUNT, TWISTER, BILL_PAXTON, APOLLO, TOM_HANKS]
```

#### TC-28 — An excluded entity is unavailable even though the chain is clean

Hard mode: the match layer has seeded entities played in earlier rounds. Neither move below appears in
this round's chain, and both are valid connections — the exclusion set is the only thing that can end
the round on them.

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=0, playerCount=2,
                          excludedMovieIds={"Q10"})
WHEN   result = playMove(state, CAST_AWAY)      # "Q1" ∈ castIds, and Q10 is not in the chain
THEN   result is RoundOver
       result.reason == Repeat
       result.loserIndex == 0
       result.losingMove == CAST_AWAY
       result.chain == [TOM_HANKS]

GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=1, playerCount=2,
                          excludedActorIds={"Q2"})
WHEN   result = playMove(state, HELEN_HUNT)     # "Q2" ∈ CAST_AWAY.castIds, not in the chain
THEN   result is RoundOver
       result.reason == Repeat
       result.loserIndex == 1
       result.losingMove == HELEN_HUNT
       result.chain == [TOM_HANKS, CAST_AWAY]
```

Both clauses of [R5](#r5--availability-repeats-and-exclusions) produce the same `RoundEndReason`
(`Repeat`). The engine does not distinguish "played this round" from "banned for the match" — the match
layer knows which sets it seeded, and a caller that wants distinct copy derives it.

#### TC-29 — Exclusions are per-type

Pins that the exclusion sets carry [R5](#r5--availability-repeats-and-exclusions)'s per-type scoping rather
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
checks, not from [R5](#r5--availability-repeats-and-exclusions). Without this, hard mode leaks: every round
could open on a banned entity.

```
GIVEN  state = InProgress(moves=[], currentPlayerIndex=0, playerCount=3,
                          excludedActorIds={"Q1"})
WHEN   result = playMove(state, TOM_HANKS)
THEN   result is RoundOver
       result.reason == Repeat
       result.loserIndex == 0
       result.losingMove == TOM_HANKS
       result.chain == []
```

**An opening move can end the round by being unavailable, but never by failing to connect.** The
connection check ([R6](#r6--an-unconnected-move-ends-the-round)) needs a predecessor and an empty chain
has none, so `Unconnected` is unreachable on the first submission; availability
([R5](#r5--availability-repeats-and-exclusions)) always runs, so a seeded exclusion can end the round
on it.

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
WHEN   result = forfeit(state, GaveUp)
THEN   result is RoundOver
       result.loserIndex == 1
       result.losingMove is null
       result.chain == [TOM_HANKS]
       result.reason == GaveUp
```

#### TC-34 — The forfeit reason reaches the result unchanged

Both `ForfeitReason` values produce an otherwise identical `RoundOver`. The reason is the *only*
observable difference, which is the point: the match layer can charge a lapsed deadline differently
from a deliberate give-up, and nothing else in the record distinguishes them.

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=1, playerCount=2)
WHEN   a = forfeit(state, GaveUp)
       b = forfeit(state, DeadlineLapsed)
THEN   a.reason == GaveUp
       b.reason == DeadlineLapsed
       a.loserIndex == b.loserIndex == 1
       a.chain == b.chain == [TOM_HANKS]
       a.losingMove is null and b.losingMove is null
```

The engine performs no validation on the reason and consults no clock
([R7](#r7--forfeit-ends-the-round), [R10](#r10--the-engine-is-pure)). If a type system can express
`ForfeitReason` as a proper subset of `RoundEndReason`, passing `Unconnected` here must not compile;
otherwise it raises a programming error under
[R15](#r15--malformed-input-is-an-error-never-a-round-outcome), never a `RoundOver`.

#### TC-24 — Operations are inapplicable to a terminal state

**[static]** In a language whose type system can express this — the operation's parameter type is
`InProgress`, and `RoundState` is a closed sum — the constraint is enforced at compile time and this
case needs no runtime test. Record it as satisfied statically and move on.

Otherwise:

```
GIVEN  terminal = RoundOver(loserIndex=1, chain=[TOM_HANKS], losingMove=null, reason=GaveUp)
WHEN   playMove(terminal, CAST_AWAY)
THEN   raises a programming error
       does NOT return a RoundState             # R15 — not an InProgress, and not a RoundOver

WHEN   forfeit(terminal, GaveUp)
THEN   raises a programming error
```

An engine that answered with a `RoundState` for a call on a terminal state would convert a programming
error into a routine result and lose the defect.

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
WHEN   result = forfeit(state, GaveUp)
THEN   result is RoundOver
       result.loserIndex == 2                   # the player on turn, not a neighbor
       result.chain == [TOM_HANKS]
       result.reason == GaveUp
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
       result.reason == Unconnected
```

The same must hold for `forfeit(state, GaveUp)` at each index, with `losingMove` null and `reason`
`GaveUp`.

---

### Group F — Purity

#### TC-18 — The input state is not mutated

```
GIVEN  state = InProgress(moves=[HELEN_HUNT, TWISTER, BILL_PAXTON], currentPlayerIndex=1, playerCount=2)
       before = deep_copy(state)
WHEN   playMove(state, APOLLO)                   # accepted -> InProgress
       playMove(state, CAST_AWAY)                # unconnected -> RoundOver
       playMove(state, TWISTER)                  # a round-ending repeat mutates nothing either
       forfeit(state, GaveUp)
THEN   state == before                          # unchanged after all four calls
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
