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

> **`:core` is no longer in the tree.** It was superseded by [ADR 025](DECISIONS.md) and the `kotlin/`
> directory was deleted; the code is at tag `kotlin-android-mvp`. Every reference to `:core`, its test
> suite, or its type signatures below is **dated record of what this spec was reconciled against** — it
> is not a description of anything a new implementation must match or avoid. **The rules R1–R17 and the
> numbered conformance suite are the whole of what binds an implementation**, and they are complete
> without the prototype columns. Read the `Implemented` column of the coverage map as "the prototype
> did," never as "the system does."

---

## Scope: the round engine, not the match

The system has two layers. This document specifies **only the lower one**.

**The round engine** builds one chain. It accepts an opening move, rotates turns among N players,
validates each submission against the previous move, and — when a player submits a move that does not
connect, or gives up, or lets a deadline lapse — ends the round and reports **who failed**. That is the
whole of its job.

Not every refused submission ends the round. A repeat or a wrong-type submission is **rejected** and
the round continues; only an unconnected move loses it. See [Move outcomes](#move-outcomes).

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
one test. Translate the fixtures once into a shared fixture module, then translate each case's
GIVEN/WHEN/THEN literally. Keep the `TC-nn` identifier in the test name so coverage stays traceable
to this document.

Two markers exempt a case from being a runtime test, and they are not the same:

- **[static]** — the type system enforces this in any implementation whose sum types are closed, so no
  runtime test is expected. Only [TC-24](#tc-24--operations-are-inapplicable-to-a-terminal-state).
- **[static-eligible]** — exempt *only* if the engine enforces type alternation statically
  ([R4](#r4--same-type-consecutive-moves-are-rejected)); the case's WHEN clause will not compile there.
  An engine that checks type at runtime must still test it. Either way, the `Rejected(WrongType)`
  behavior is tested at the boundary that deserializes untyped input, because that is where a real
  wrong-type submission arrives.

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

Three terms are this document's own; the skill and the prototype have no equivalent.

| Term | Meaning |
|---|---|
| **Rejected** | A submission refused without ending the round — a repeat or the wrong type. The state is unchanged and the player on turn may submit again ([R16](#r16--a-rejected-submission-leaves-the-round-unchanged)) |
| **Unconnected** | A submission of the correct type, available, that has no edge to the previous move. This is the only way `playMove` ends a round |
| **Available** | Not already played in this round and not in the match layer's exclusion set for its type ([R5](#r5--availability-repeats-and-exclusions)) |

**Graph membership defines validity, not real-world truth.** An edge the artifact does not carry is
not a legal move, however true it is off-graph. The engine tests `castIds` and nothing else
([R12](#r12--identity-is-the-id-alone)), and `castIds` comes from a graph built offline with a cast
cap, so a real but obscure cast member is absent from the graph and is therefore not a valid move.
This is a property of the data the engine is handed, not a rule the engine applies — it is stated here
because it is the one place a reader is likely to mistake a correct rejection for a bug. The cap is a
dial (`cast_cap`, `min_cast` — [etl/AGENTS.md](../etl/AGENTS.md)), and expect the argument to recur in
playtests.

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
    losingMove:   Move?                # null unless the round ended Unconnected
    reason:       RoundEndReason

Rejected:
    reason:       RejectionReason      # carries no state — the caller still holds the input

RoundEndReason  = Unconnected | GaveUp | DeadlineLapsed
RejectionReason = WrongType | Repeat
ForfeitReason   = GaveUp | DeadlineLapsed      # the RoundEndReason values forfeit may produce

RoundState  = InProgress | RoundOver           # what a caller persists
MoveOutcome = InProgress | Rejected | RoundOver
```

**`Rejected` is not a state.** It reports that the submission was refused; the round is still the
`InProgress` value the caller passed in. Modelling it as a third `RoundState` variant would let a
caller persist "rejected" as though it were a position in the game
([R16](#r16--a-rejected-submission-leaves-the-round-unchanged)).

**`ForfeitReason` is a proper subset of `RoundEndReason`.** `Unconnected` is unreachable through
`forfeit`, and a type system that can express the subset should — passing `Unconnected` to `forfeit`
is a caller error, not a round outcome.

**`RoundOver` carries no winner.** See [R8](#r8--loser-determination) and
[S3](#s3--the-round-result-names-no-winner-structural-not-a-test-case).

**Why `reason` exists.** The match layer charges penalties, and the penalties differ. A correspondence
player who lets a three-day deadline lapse has not made the same choice as one who taps "give up," and
both differ from one who guessed wrong — yet all three produce `RoundOver` with the same loser. Only
`Unconnected` is derivable from the rest of the record (`losingMove != null`); deriving it from a null
would make the match layer's penalty table pattern-match on the absence of a field, so the reason is
explicit for all three.

**The exclusion sets are how a match forbids reuse across rounds.** Both default to empty, which is
the default mode: a new round starts with every entity available again. A mode that forbids reuse for
the whole match seeds them with everything played in earlier rounds. The engine does not know which
mode is in play — it reads two sets and applies [R5](#r5--availability-repeats-and-exclusions). Populating
them is the match layer's job; see [Engine boundary](#engine-boundary).

**Player indices are positions in a roster fixed for the round.** The engine never adds or removes
players mid-round, so an index is stable from the opening move to the round's end. A match layer that
drops an eliminated player does so *between* rounds, by starting the next round with a smaller
`playerCount`.

## Operations

```
playMove(state: InProgress, move: Move)            -> MoveOutcome   # InProgress, Rejected, or RoundOver
forfeit(state: InProgress, reason: ForfeitReason)  -> RoundOver
```

Both are pure functions of their arguments. Neither performs I/O. Neither mutates its input.

`forfeit` means "the player on turn cannot continue this round" — an explicit give-up, or a deadline
the session layer has adjudicated as lapsed. It concedes **the round, not the match**; a player
quitting the match outright is a match-layer event that happens to end the current round this way.

**`forfeit` takes the reason because the engine cannot infer it.** [R10](#r10--the-engine-is-pure)
denies the engine a clock, so it cannot tell a give-up from a lapse; the session layer knows which one
it is adjudicating and says so. This is the one piece of caller intent the engine records without
verifying.

### Move outcomes

`playMove` either raises an error or returns exactly one of three outcomes. They differ in what the
caller persists and in whether the player on turn keeps the turn. The error row is listed for
completeness — it is raised, never returned
([R15](#r15--malformed-input-is-an-error-never-a-round-outcome)).

| Outcome | Cause | Turn advances | Caller persists | Round ends |
|---|---|---|---|---|
| **Error** | [R13](#r13--invalid-state-and-move-construction-is-rejected)/[R14](#r14--operations-are-inapplicable-to-terminal-states) violations — blank ID, terminal state | — | nothing | no — programming error ([R15](#r15--malformed-input-is-an-error-never-a-round-outcome)) |
| **Rejected** | Wrong type ([R4](#r4--same-type-consecutive-moves-are-rejected)) or unavailable ([R5](#r5--availability-repeats-and-exclusions)) | no | nothing | no ([R16](#r16--a-rejected-submission-leaves-the-round-unchanged)) |
| **InProgress** | Accepted | yes | the new state | no |
| **RoundOver** | Unconnected ([R6](#r6--an-unconnected-move-ends-the-round)), or `forfeit` ([R7](#r7--forfeit-ends-the-round)) | — | the terminal state | yes |

**Evaluation order is normative: type, then availability, then connection.** A submission failing more
than one check resolves to the *first* failure in that order, so a rejection always wins over a round
loss. This is why order matters rather than being an implementation detail: a player who submits an
already-played entity that also would not have connected gets a retry, not a loss.

*Rationale:* rejection means "the client should never have sent this." A repeat is that regardless of
whether it also fails to connect, and the client-side prevention that normally catches it would have
fired before any connection was evaluated. Resolving such a submission to a loss would charge a player
for a defect in their client — the same reasoning as
[R15](#r15--malformed-input-is-an-error-never-a-round-outcome), one category out.

**A rejection is not a game event.** It is not a miss, not a strike, not a turn. The match layer never
sees one; a conforming session layer returns it to the submitting client as an error and leaves the
stored state untouched.

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

### R4 — Same-type consecutive moves are rejected

`Actor` after `Actor`, or `Movie` after `Movie`, is refused regardless of IDs. The chain strictly
alternates.

The outcome is `Rejected(WrongType)`, **not** a round loss: the required type is fully determined by
the chain, the player can see it, and a client that offers the wrong one has malfunctioned. Charging a
loss for that would penalize the player for their client's defect.

**This rule may be enforced by the type system instead of at runtime.** An engine whose `InProgress`
is split by required type — so that `playMove` on a state awaiting an Actor accepts only an `Actor` —
makes a wrong-type submission a compile error, and needs no runtime branch for it. It must still
produce `Rejected(WrongType)` at the boundary where untyped input becomes a `Move`; static enforcement
relocates the check, it does not remove it. The same MAY/MUST split as
[R14](#r14--operations-are-inapplicable-to-terminal-states).

### R5 — Availability: repeats and exclusions

A move is **available** iff no move **of the same type** with the same `id` already appears anywhere in
the chain, and its `id` does not appear in the exclusion set for its type:

```
isAvailable(move, state) =
    match move:
        Actor -> move.id ∉ state.excludedActorIds
                 and none(m.id == move.id for m in state.moves where m is Actor)
        Movie -> move.id ∉ state.excludedMovieIds
                 and none(m.id == move.id for m in state.moves where m is Movie)
```

An unavailable move is `Rejected(Repeat)`.

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

Unlike [R4](#r4--same-type-consecutive-moves-are-rejected), **this rule cannot be enforced by a type
system.** Availability is a predicate over a runtime set; no type discipline available in a practical
implementation language can express "this id is not in that collection." It is always a runtime check.

### R6 — An unconnected move ends the round

The round ends immediately when a move of the correct type ([R4](#r4--same-type-consecutive-moves-are-rejected))
that is available ([R5](#r5--availability-repeats-and-exclusions)) is nonetheless not a valid connection
to the previous move ([R2](#r2--actor-after-movie)/[R3](#r3--movie-after-actor)). `RoundOver.reason` is
`Unconnected`.

**This is the only way `playMove` ends a round.** Wrong type and unavailability are rejections
([R16](#r16--a-rejected-submission-leaves-the-round-unchanged)); malformed input is an error
([R15](#r15--malformed-input-is-an-error-never-a-round-outcome)). A player loses a round by naming
something plausible that turns out not to connect — which is the failure the game is about.

Note the asymmetry, which follows from [R1](#r1--the-opening-move-is-not-connection-checked): the
connection check requires a predecessor and so is skipped on an empty chain, while the availability
check always runs. **An opening move can therefore be rejected but never lose the round** — in a mode
that seeded exclusions ([TC-30](#tc-30--exclusions-apply-to-the-opening-move)).

`RoundOver.losingMove` is the unconnected move. `RoundOver.chain` holds the moves accepted **before**
it — the losing move is never appended.

### R7 — Forfeit ends the round

`forfeit` ends the round immediately. `RoundOver.losingMove` is null, `RoundOver.chain` is the chain
unchanged, and `RoundOver.reason` is the `ForfeitReason` the caller supplied — `GaveUp` or
`DeadlineLapsed`.

The engine does not distinguish the two itself and must not try: [R10](#r10--the-engine-is-pure) leaves
it no clock. It records what the session layer tells it.

### R8 — Loser determination

```
loserIndex = currentPlayerIndex
```

The player on turn is the player who failed, whether by an unconnected move
([R6](#r6--an-unconnected-move-ends-the-round)) or by forfeit ([R7](#r7--forfeit-ends-the-round)).
This holds at every `playerCount` — there is no arithmetic and no special case for N > 2.

A rejected submission names no loser, because it ends nothing
([R16](#r16--a-rejected-submission-leaves-the-round-unchanged)).

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
from normal results. They must never be reported as **any** `MoveOutcome` — not a `RoundOver`, and not
a `Rejected` either.

*Rationale:* a malformed input silently resolving to a loss would end real rounds incorrectly and
charge a strike to a player who did nothing wrong. Reporting one as `Rejected` is the subtler version
of the same fault: it converts a programming error into a routine, retryable response, and the defect
is never surfaced.

[R16](#r16--a-rejected-submission-leaves-the-round-unchanged) extends the same reasoning one category
out, to submissions that are well-formed but should never have been sent.

### R16 — A rejected submission leaves the round unchanged

When `playMove` returns `Rejected`, **nothing about the round changes**: the chain does not grow, the
turn does not advance, `currentPlayerIndex` is untouched, and no round result exists. The player on
turn may submit again.

`Rejected` carries no state. The caller still holds the `InProgress` value it passed in and must
continue from that value — a session layer persists nothing and returns an error to the submitting
client.

*Rationale:* the two rejection causes ([R4](#r4--same-type-consecutive-moves-are-rejected),
[R5](#r5--availability-repeats-and-exclusions)) describe submissions a correct client cannot produce.
Both are prevented client-side and re-checked server-side; the engine is the last of three lines, not
the first. A round outcome at that position would mean a player loses because their client, not their
recall, failed.

**The engine imposes no limit on rejections.** A player may submit rejected moves indefinitely and the
engine will refuse each one, timelessly. What bounds this is the turn deadline, which the engine cannot
see — see [R17](#r17--every-round-terminates).

### R17 — Every round terminates

Two guarantees, held by different layers. **Neither alone is sufficient**, and only the first belongs
to the engine.

**The chain is finite — the engine guarantees this.** Every accepted move permanently consumes one
entity of its type from a finite corpus ([R5](#r5--availability-repeats-and-exclusions), clause 1), and
[R4](#r4--same-type-consecutive-moves-are-rejected) forces the types to alternate, so the set of
available entities strictly decreases with each accepted move and the chain cannot exceed
`2 × min(|actors|, |movies|) + 1`.

Without clause 1 that bound does not exist: a chain can cycle between the same two entities forever.
This is the whole reason clause 1 is not configurable, and it is why "repeats are on" is a property of
the engine rather than a setting a mode may choose.

**The turn is bounded — the session layer guarantees this.** The engine cannot bound a round on its
own, because a rejected submission consumes nothing
([R16](#r16--a-rejected-submission-leaves-the-round-unchanged)) and the engine has no clock
([R10](#r10--the-engine-is-pure)). A player who submits repeats forever is refused forever. Only the
turn deadline ends that, and it lives in the session layer, which resolves a lapse to
`forfeit(state, DeadlineLapsed)`.

**A rejected submission must not extend or reset the deadline.** Resetting it would remove the only
bound on the retry loop and make a round genuinely non-terminating. This is a session-layer obligation;
it is stated here because the engine change that introduced rejections is what created the need for it.

*The bound is a proof, not a limit.* Roughly 95,000 moves is not a useful cap on a real round — see
[Chain length limits](#open-questions), which this does not settle.

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
| Whether entities reuse across rounds — and seeding `excludedActorIds` / `excludedMovieIds` accordingly | Match layer; the engine applies the sets it is given ([R5](#r5--availability-repeats-and-exclusions)) |
| Requiring the opening move to be an Actor, if a mode wants it | Caller (session / UI layer) |
| The player is offered the correct entity type each turn | Caller filters its typeahead to the required type; [R4](#r4--same-type-consecutive-moves-are-rejected) is the engine's backstop, and a wrong type reaching it means the client malfunctioned |
| The player is not offered an entity already played, or excluded | Caller filters its typeahead against the chain and the exclusion sets; [R5](#r5--availability-repeats-and-exclusions) is the backstop |
| `castIds` is accurate and complete | Caller populates from the graph before constructing the move |
| Name resolution, typos, disambiguation | Caller, before a `Move` exists |
| **Bounding the turn, so the round terminates** | **Session layer, via the deadline. The engine bounds the chain but not the retry loop — [R17](#r17--every-round-terminates)** |
| **Deciding whether a forfeit is `GaveUp` or `DeadlineLapsed`** | **Session layer; it passes the reason to `forfeit`. The engine has no clock ([R10](#r10--the-engine-is-pure))** |
| **Rate-limiting rejected submissions** | **Session layer / transport. Rejections are unbounded at the engine by design ([R16](#r16--a-rejected-submission-leaves-the-round-unchanged))** |
| Mapping a deadline expiry or an abandonment onto a round result | Session layer; it calls `forfeit` ([ADR 012](DECISIONS.md), as amended by [ADR 018](DECISIONS.md) — one deadline model, no running clock) |
| Detecting that the player on turn has no legal move at all | Session layer; it holds the graph. The engine cannot see it when the chain head is an Actor — see [Open questions](#open-questions) |
| Persistence, transport, presence | Session layer |

**"Appeared in" is defined by the graph, not by the engine.** `castIds` reflects what the ETL
artifact carries — truthy `wdt:P161`, capped at `cast_cap`. A real but absent cast member is not a
legal move. That is a data dial, not an engine rule.

**The caller's two filters are what make rejections rare, and they do not disclose an answer.** The
required type and the played set are both information the player already holds — the rules dictate the
type, and the chain is on their screen. Filtering the typeahead by them is a UX affordance, not a hint.
Filtering by the previous entity's *neighbours* would hand over the answer and is forbidden
([ADR 020](DECISIONS.md), [AGENTS.md](../AGENTS.md)). The line: **filter on what the player already
knows; never filter on what only the graph knows.** The engine is indifferent either way — it re-checks
both — but a caller that skips the filters turns [R4](#r4--same-type-consecutive-moves-are-rejected)
and [R5](#r5--availability-repeats-and-exclusions) from backstops into a routine failure path.

**Move attribution is derivable, not stored.** `RoundOver.chain` records moves, not who played them.
A caller that needs per-move attribution computes it from the round's opening player index and
[R9](#r9--player-rotation): move `i` was played by `(openingPlayerIndex + i) % playerCount`. The match
layer knows the opening index because it started the round — and in practice it is always zero, since
the match layer builds every roster opener-first
([MATCH_CONFORMANCE.md M8](MATCH_CONFORMANCE.md#m8--the-round-roster-is-derived-never-stored)), leaving
`roster[i % playerCount]`.

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
([R6](#r6--an-unconnected-move-ends-the-round)) and that `reason` is the expected `RoundEndReason`.

Every case asserting `Rejected` must also assert that the round is unchanged — same chain, same
`currentPlayerIndex` ([R16](#r16--a-rejected-submission-leaves-the-round-unchanged)). The cases below
state the reason and leave the unchanged-state assertion implied by
[TC-32](#tc-32--a-rejection-leaves-the-round-unchanged), which pins it once in full.

**Two properties hold across the suite; preserve both when translating.**

*Every GIVEN chain is legally reachable.* Each fixture chain could have been produced by playing its
moves in order from an empty chain — every adjacent pair alternates type and connects. A case that
asserts behavior from an unreachable chain proves nothing about a real round. `currentPlayerIndex` is
independent: the engine keeps no record of who played which move, so any in-range index is a valid
state to test, and several cases set one that does not match the chain's length.

*Each case isolates one rule.* Where a move could fail more than one check, the fixtures are chosen so
exactly one applies — a repeat case is a valid connection of the correct type, so an engine with no
availability check fails it rather than passing by accident.
[TC-20](#tc-20--rejection-precedence-type-before-availability) and
[TC-33](#tc-33--rejection-takes-precedence-over-a-round-loss) are the two exceptions; stacking causes
is precisely the behavior they exist to pin. Do not "simplify" a fixture during translation; the
specific IDs are load-bearing.

**Cases marked [static-eligible]** may be satisfied by the type system rather than a runtime test, per
[R4](#r4--same-type-consecutive-moves-are-rejected) — an engine that splits `InProgress` by required
type cannot express the WHEN clause. Record such a case as satisfied statically, and test the
`Rejected(WrongType)` behavior at the boundary that deserializes untyped input instead.

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

### Group C — Rejections: type and availability

**No case in this group ends the round.** Each pins that a refused submission leaves the round exactly
as it was, per [R16](#r16--a-rejected-submission-leaves-the-round-unchanged). This is the group that
changed most against the prototype, which resolved every one of these to a loss.

#### TC-09 — Actor after actor

**[static-eligible]**

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=1, playerCount=2)
WHEN   result = playMove(state, HELEN_HUNT)
THEN   result is Rejected
       result.reason == WrongType
```

#### TC-10 — Movie after movie

**[static-eligible]** Refused on type grounds ([R4](#r4--same-type-consecutive-moves-are-rejected))
even though `TOY_STORY.castIds` contains `"Q1"`. An implementation that checked cast membership without
checking type would wrongly *accept* it.

```
GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOY_STORY)
THEN   result is Rejected
       result.reason == WrongType
```

#### TC-05 — Repeat actor

The submitted move is the correct type for the turn and a valid connection. Availability is the only
thing that can refuse it, so an engine missing [R5](#r5--availability-repeats-and-exclusions) fails here
rather than passing incidentally.

```
GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOM_HANKS)
       # Actor after Movie -> type alternation holds
       # "Q1" ∈ CAST_AWAY.castIds -> connection holds
THEN   result is Rejected
       result.reason == Repeat
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
THEN   result is Rejected
       result.reason == Repeat
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
       # connection holds ("Q1" ∈ CAST_AWAY.castIds); only identity-by-id can refuse it
THEN   result is Rejected                            # same id as TOM_HANKS -> unavailable
       result.reason == Repeat
```

#### TC-16 — Availability scans the entire chain

The repeat is at index 0 of a six-move chain, five moves behind the one being checked — not a recent
move. An engine comparing only against the tail passes [TC-05](#tc-05--repeat-actor) and fails here.

```
GIVEN  state = InProgress(moves=LONG_CHAIN, currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, TOM_HANKS)
       # previous move is APOLLO and "Q1" ∈ APOLLO.castIds -> the connection is valid
THEN   result is Rejected
       result.reason == Repeat
```

#### TC-20 — Rejection precedence: type before availability

**[static-eligible]** The first of two cases that deliberately stack causes. `CAST_AWAY` here is *both*
unavailable and the wrong type. Both are rejections, so the round survives either way; what this pins
is the **reason** the caller is told, and therefore the evaluation order in
[Move outcomes](#move-outcomes) — type is checked first.

The reason is not cosmetic: it is what the client shows the player, and "you already used that" for a
submission that was actually the wrong type sends them looking for the wrong mistake.

```
GIVEN  state = InProgress(
           moves=[TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER],
           currentPlayerIndex=0, playerCount=2)
WHEN   result = playMove(state, CAST_AWAY)
       # same-type-consecutive (Movie after TWISTER, a Movie) -> R4
       # AND unavailable ("Q10" already in the chain)         -> R5
THEN   result is Rejected
       result.reason == WrongType                    # R4 is evaluated before R5
```

Under static enforcement this case is unreachable — the WHEN clause will not compile — and the
precedence it pins is enforced by construction. Record it as satisfied statically.

#### TC-33 — Rejection takes precedence over a round loss

The second stacked case, and the one that decides whether a player keeps the round. `TWISTER` is the
correct type for the turn, is **already in the chain**, and **would not have connected** either.
Availability is evaluated before connection, so the submission is refused and the round survives.

An engine that evaluated the connection first would end the round here — charging a loss for a
submission a working client would never have sent. This is the case that makes the evaluation order in
[Move outcomes](#move-outcomes) observable.

```
GIVEN  state = InProgress(
           moves=[HELEN_HUNT, TWISTER, BILL_PAXTON, APOLLO, TOM_HANKS],
           currentPlayerIndex=1, playerCount=2)
       # Q2 -> {Q2,Q3} -> Q3 -> {Q1,Q3} -> Q1 : valid at every step

WHEN   result = playMove(state, TWISTER)
       # Movie after Actor                    -> R4 passes, type is correct
       # "Q50" already in the chain           -> R5 fails
       # "Q1" ∉ TWISTER.castIds {"Q2","Q3"}   -> R6 would also have failed

THEN   result is Rejected                     # availability precedes connection
       result.reason == Repeat
       # NOT RoundOver — the player keeps both the round and the turn
```

#### TC-28 — An excluded entity is unavailable even though the chain is clean

Hard mode: the match layer has seeded entities played in earlier rounds. Neither move below appears in
this round's chain, and both are valid connections — the exclusion set is the only thing that can
refuse them.

```
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=0, playerCount=2,
                          excludedMovieIds={"Q10"})
WHEN   result = playMove(state, CAST_AWAY)      # "Q1" ∈ castIds, and Q10 is not in the chain
THEN   result is Rejected
       result.reason == Repeat

GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=1, playerCount=2,
                          excludedActorIds={"Q2"})
WHEN   result = playMove(state, HELEN_HUNT)     # "Q2" ∈ CAST_AWAY.castIds, not in the chain
THEN   result is Rejected
       result.reason == Repeat
```

Both clauses of [R5](#r5--availability-repeats-and-exclusions) produce the same `RejectionReason`. The
engine does not distinguish "played this round" from "banned for the match" — the match layer knows
which sets it seeded, and a caller that wants distinct copy derives it.

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
THEN   result is Rejected
       result.reason == Repeat
```

**An opening move can be rejected but can never lose the round.** The only round-ending outcome from
`playMove` is `Unconnected` ([R6](#r6--an-unconnected-move-ends-the-round)), and an empty chain has no
predecessor to connect to. A round cannot end on its first submission.

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

#### TC-32 — A rejection leaves the round unchanged

Pins [R16](#r16--a-rejected-submission-leaves-the-round-unchanged) once, in full, for both rejection
reasons — the assertion every other case in
[Group C](#group-c--rejections-type-and-availability) implies. The turn does **not** advance: the same
player is still on turn and may submit again.

```
GIVEN  state = InProgress(moves=[TOM_HANKS, CAST_AWAY], currentPlayerIndex=0, playerCount=3)
       before = deep_copy(state)

WHEN   result = playMove(state, TOM_HANKS)      # unavailable: already in the chain
THEN   result is Rejected
       state == before                          # input untouched (R10)
       # the caller's state is still `before`; no new InProgress was produced

WHEN   the caller continues from the same state and submits a legal move
       result = playMove(state, HELEN_HUNT)     # "Q2" ∈ CAST_AWAY.castIds, not yet played
THEN   result is InProgress
       result.moves == [TOM_HANKS, CAST_AWAY, HELEN_HUNT]
       result.currentPlayerIndex == 1           # advanced from 0 exactly once, not twice
```

The second WHEN is what makes the case meaningful: an engine that advanced the turn on the rejection
would produce `currentPlayerIndex == 2` here, silently skipping a player.

#### TC-24 — Operations are inapplicable to a terminal state

**[static]** In a language whose type system can express this — the operation's parameter type is
`InProgress`, and `RoundState` is a closed sum — the constraint is enforced at compile time and this
case needs no runtime test. Record it as satisfied statically and move on.

Otherwise:

```
GIVEN  terminal = RoundOver(loserIndex=1, chain=[TOM_HANKS], losingMove=null, reason=GaveUp)
WHEN   playMove(terminal, CAST_AWAY)
THEN   raises a programming error
       does NOT return a MoveOutcome            # R15 — not a RoundOver, and not a Rejected either

WHEN   forfeit(terminal, GaveUp)
THEN   raises a programming error
```

Note `Rejected` is included in what must not be returned. An engine that answered "rejected" for a
call on a terminal state would convert a programming error into a routine, retryable response.

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
GIVEN  state = InProgress(moves=[TOM_HANKS], currentPlayerIndex=1, playerCount=2)
       before = deep_copy(state)
WHEN   playMove(state, CAST_AWAY)
       playMove(state, OUTSIDER)
       playMove(state, TOM_HANKS)               # a rejection mutates nothing either
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

---

## Coverage map

Status of the Kotlin `:core` suite as of tag `kotlin-android-mvp`, at
`kotlin/core/src/jvmTest/kotlin/me/zwsmith/core/GameEngineTest.kt`. That path is not in this tree —
see the note at the top. Behavior columns describe the prototype, not the test.

| TC | Scenario | Rules | Implemented | Tested |
|---|---|---|---|---|
| 01 | Valid movie after actor | R2, R9 | yes | yes |
| 02 | Valid actor after movie | R3, R9 | yes | yes |
| 03 | Movie excludes previous actor | R3, R6 | yes | yes ² ⁴ |
| 04 | Actor absent from cast | R2, R6 | yes | yes ² ⁴ |
| 05 | Repeat actor | R5, R16 | **no** ⁵ | partial ¹ |
| 06 | Repeat movie | R5, R16 | **no** ⁵ | no |
| 07 | Giving up | R7, R8 | partial ⁴ | yes ² |
| 08 | Opening move accepted | R1 | yes | no |
| 09 | Actor after actor | R4, R16 | **no** ⁵ | no |
| 10 | Movie after movie | R4, R16 | **no** ⁵ | no |
| 11 | Cross-type ID collision | R5 | yes | no |
| 12 | Rotation wraps, N > 2 | R8, R9 | partial ² | no |
| 13 | Opening move may be a movie | R1 | yes | no |
| 14 | Connection vs. last move only | R11 | yes | no |
| 15 | Identity is the ID | R12, R16 | **no** ⁵ | no |
| 16 | Availability scans whole chain | R5, R16 | **no** ⁵ | no |
| 17 | Empty cast connects to nothing | R2, R3 | yes | no |
| 18 | Input not mutated | R10 | yes | no |
| 19 | Determinism | R10 | yes | no |
| 20 | Rejection precedence: type first | R4, R5 | **no** ⁵ | no |
| 21 | Reject `playerCount < 2` | R13, R15 | **no** | no |
| 22 | Reject out-of-range index | R13, R15 | **no** | no |
| 23 | Reject blank entity ID | R13, R15 | **no** | no |
| 24 | Terminal state inapplicable | R14, R15 | yes (static) | n/a |
| 25 | Full round from an empty chain | R1, R2, R3, R9 | yes | no |
| 26 | Rotation cycle at N = 4 | R9 | yes | no |
| 27 | Loser is the player on turn | R8 | **no** ² | no |
| 28 | Excluded entity is unavailable | R5, R16 | **no** ³ | no |
| 29 | Exclusions are per-type | R5 | **no** ³ | no |
| 30 | Exclusions apply to the opener | R1, R5, R16 | **no** ³ | no |
| 31 | Exclusions default to empty | R5 | n/a ³ | no |
| 32 | Rejection leaves round unchanged | R16 | **no** ⁵ | no |
| 33 | Rejection precedes a round loss | R5, R6, R16 | **no** ⁵ | no |
| 34 | Forfeit reason reaches the result | R7 | **no** ⁴ | no |
| S1 | No I/O dependency | R10 | yes | structural |
| S2 | IDs opaque end to end | — | **no** — `:core` declares `Int` | structural |
| S3 | Result names no winner | R8 | **no** ² | structural |

¹ `GameEngineTest.kt:72` submits a repeat actor directly after another actor, so the move fails
[R4](#r4--same-type-consecutive-moves-are-rejected) whether or not any availability check exists.
It asserts the right outcome for the wrong reason. Under this document the fixture is worse than
imprecise: type precedes availability ([Move outcomes](#move-outcomes)), so it would yield
`Rejected(WrongType)` and never reach [R5](#r5--availability-repeats-and-exclusions) at all —
the shape [TC-20](#tc-20--rejection-precedence-type-before-availability) now exists to pin.
[TC-05](#tc-05--repeat-actor) replaces it with a fixture that isolates R5.

² The prototype reports `winnerIndex = (currentPlayerIndex - 1 + playerCount) % playerCount` instead
of a loser. At `playerCount == 2` that value coincides with "the player who did not fail," so the
two-player cases pass under either contract; above two players it is wrong, and the contract itself is
wrong at every N ([S3](#s3--the-round-result-names-no-winner-structural-not-a-test-case)).

³ The prototype has no exclusion sets; its repeat check scans the chain only. Its behavior is
equivalent to the default mode, so TC-31 is satisfied by construction while TC-28/29/30 are
unimplementable against it.

⁴ The prototype's `RoundOver` equivalent carries no `reason`, and its forfeit takes no argument. Every
case asserting a `RoundEndReason` is a delta, including ones the prototype otherwise passes.

⁵ **The rejection taxonomy is entirely absent from the prototype**, which resolves a repeat or a
wrong-type submission to a round loss. These cases do not merely lack tests — the prototype implements
the opposite outcome, and an engine ported from it unchanged fails them.

Six deltas against the prototype: **the rejection taxonomy** (R4, R5, R16 and Group C — the largest,
and the one that inverts existing behavior), **round-end reasons** (R7, `RoundOver.reason`, TC-34),
**the winner/loser contract** (R8, S3, and every `RoundOver` assertion), **cross-round exclusions**
(R5's second clause, TC-28–30), **Group G** (R13 construction validation is absent), and **S2**
(`:core` types IDs as `Int`, a TMDB-era leftover — [ADR 016](DECISIONS.md)).

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
([ADR 010](DECISIONS.md)); the graph artifact emits QID strings, and
[ADR 016](DECISIONS.md) makes the data authoritative over the stale `:core` signature.

**TC-11's fixtures.** The retired spec's TC-11 restated itself three times before landing on a usable
form. This document uses the final `state3` shape, and adds the note that QIDs make the collision
impossible in real data — which is why the case survives as a semantics test rather than being cut.

**Repeat-case fixtures are not the Kotlin suite's.** The existing repeat test submits the repeated
actor immediately after another actor, so [R4](#r4--same-type-consecutive-moves-are-rejected) fires
before [R5](#r5--availability-repeats-and-exclusions) is ever consulted — an engine with the
availability check deleted still passes. [TC-05](#tc-05--repeat-actor), [TC-06](#tc-06--repeat-movie),
and [TC-15](#tc-15--identity-is-the-id-display-metadata-is-ignored) use fixtures where the move is a
legal continuation in every other respect, so only R5 can refuse it.

**Defensive validation.** [R13](#r13--invalid-state-and-move-construction-is-rejected)/[R15](#r15--malformed-input-is-an-error-never-a-round-outcome)
are new requirements, not a record of existing behavior — see Group G.

**Rejections are new, and they invert prior behavior.** Every source — the skill, the prototype, and
the retired spec — treats a repeat and a wrong-type submission as ways to lose a round. This document
makes both `Rejected`: the round continues and the player retries. The reasoning is in
[R16](#r16--a-rejected-submission-leaves-the-round-unchanged), and it is the same reasoning
[R15](#r15--malformed-input-is-an-error-never-a-round-outcome) already applied to malformed input — a
player should not lose because their client sent something a correct client cannot send. Both
conditions are prevented client-side and re-checked server-side before the engine sees them; the engine
is the last line, not the first. This is the largest behavioral delta in the document.

**R5's clauses were separated after being briefly unified.** An earlier framing treated in-round
repeats and cross-round exclusions as one policy, on the grounds that both are "entities unavailable to
this round" and both look like match-layer configuration. That is wrong: in-round repeat prohibition is
the sole guarantee that a round terminates ([R17](#r17--every-round-terminates)), so it cannot be
configurable, while cross-round exclusions carry no such load and remain optional. They share an
implementation and a `RejectionReason`, not a justification. Recorded because the unified framing is
the more natural-looking one and will be re-proposed.

**Round termination was never stated.** No source document asserts that a round ends. The property was
implicit in repeat detection and became load-bearing only once rejections made it possible to submit
indefinitely without advancing the chain. [R17](#r17--every-round-terminates) states it, and splits it
between the engine and the session layer.

---

## Open questions

Unresolved. Each needs a decision before the area it touches is built. None of them block the round
engine — they are match-layer and contract questions the round engine's output feeds.

> **Failure reason codes are no longer open.** They were this section's highest-priority question and
> are settled by [ADR 021](DECISIONS.md), which introduced the outcome taxonomy above. The question
> dissolved more than it was answered: two of the causes it sought to distinguish — repeat and wrong
> type — turned out not to be round outcomes at all ([R16](#r16--a-rejected-submission-leaves-the-round-unchanged)),
> and `Unconnected` is the only one `playMove` can now produce. What survived was the give-up/lapse
> pair, resolved by [R7](#r7--forfeit-ends-the-round)'s `ForfeitReason` parameter.

> **The opening player index is no longer open.** It is answered by
> [`MATCH_CONFORMANCE.md`](MATCH_CONFORMANCE.md), and mostly dissolved: the match layer builds every
> roster opener-first ([M8](MATCH_CONFORMANCE.md#m8--the-round-roster-is-derived-never-stored)), so the
> opening index is always zero and there is nothing to record. What a persisted result actually needs
> is *that round's roster*, which
> [M9](MATCH_CONFORMANCE.md#m9--a-seat-index-is-round-local) derives from stored match state — via
> `Removal.beforeRound` and a round-0 opener fixed at `matchOrder[0]`, both of which exist for this
> purpose. `rosterAt(match, k)` is the projection that exposes it.

> **Deadline expiry ownership is no longer open either.** [ADR 018](DECISIONS.md) reduced it to a
> reason-code question by dropping the running chess clock, and [ADR 021](DECISIONS.md) then answered
> that: a turn carries a `deadline_at` timestamp, the session layer adjudicates expiry (lazily on next
> read, or by a sweeper) and resolves it to `forfeit(state, DeadlineLapsed)`. The engine stays timeless
> ([R10](#r10--the-engine-is-pure)) and records the reason it is given
> ([R7](#r7--forfeit-ends-the-round)).
>
> One consequence survives as an obligation rather than a question: the deadline is now the **only**
> bound on the rejection retry loop ([R17](#r17--every-round-terminates)), so it must not be reset by a
> rejected submission. Note also that the adjudicator is not a player, which is one of the three
> writers the session layer's optimistic concurrency exists to serialize (`AGENTS.md`,
> [ADR 018](DECISIONS.md) §4).

**An exhausted frontier is indistinguishable from a player's failure.** Nothing in this spec expresses
"the player on turn had *no* legal move." [R6](#r6--an-unconnected-move-ends-the-round) and
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
all, which folds back into reason codes.

**Now measured, and the answer lowers the priority.** [ADR 019](DECISIONS.md) reports that while
45.9% of actor nodes in `graph/v1` are degree-1, they have a median of 4 sitelinks — a move nobody
can name is not an available move. Requiring the round-ending actor to be even modestly
recognizable puts the rate at 11% of the 100 most famous films, and 2% for a well-known actor.
**The current behaviour — the player on turn is the loser — is therefore defensible**, and this
question is open rather than blocking. Note also that a dead-end move is a *legitimate winning
move* under this project's framing, so ending the round without a strike is not obviously the
right policy: if knowing an actor has one credit is the knowledge the game tests, the loser
arguably should take the strike. Two things remain unmeasured: whether players find these moves at
all, and how the rate rises mid-chain as degree-2+ actors exhaust their alternatives.

**Chain length limits.** [R17](#r17--every-round-terminates) bounds the chain at roughly
`2 × min(|actors|, |movies|) + 1` — about 95,000 moves against `graph/v1`. That is a termination proof,
not a usable limit, and it leaves this question exactly where it was. With correspondence the only mode
([ADR 018](DECISIONS.md)), a round spanning weeks is the normal case rather than an edge case, so a
practically unbounded `moves` list is a persistence and payload concern before it is an engine one.

---

## Related documents

| Document | Relationship |
|---|---|
| [AGENTS.md](../AGENTS.md) | Architecture boundaries; which of these rules are binding vs. provisional |
| [docs/DECISIONS.md](DECISIONS.md) | ADRs 008–021. Two touch this spec directly: [ADR 018](DECISIONS.md) drops the running chess clock, leaving a single deadline model; **[ADR 021](DECISIONS.md) is the source of the outcome taxonomy** — rejections, round-end reasons, and R16/R17 |
| `movie-actor-chain-game` skill | Domain rules and vocabulary; implementation-agnostic, leaves repeats/opener/"appeared in" open — answered here and in AGENTS.md |
| [etl/AGENTS.md](../etl/AGENTS.md) | How `castIds` is produced; `cast_cap` and `min_cast` define what "appeared in" means in practice |
| [issue #17](https://github.com/zws33/bacons_law/issues/17) | The coverage gap this document supersedes |

**Not yet written:** the match-layer spec — strike accounting, mode configuration, elimination and
match-end conditions, standings. This document's [Scope](#scope-the-round-engine-not-the-match)
section defines the seam it must attach to.
