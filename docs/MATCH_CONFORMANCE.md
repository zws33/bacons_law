# Bacon's Law — Match Layer Conformance Spec

**Status:** DRAFT. Authoritative for match-layer behavior once accepted. Language- and
framework-agnostic.

This document specifies the layer above the round engine: what a round loss costs, when a match ends,
who opens each round, and how players are ranked. It is the other half of the seam that
[`ENGINE_CONFORMANCE.md`](ENGINE_CONFORMANCE.md) stops at.

It takes precedence over the match-layer summaries in [`AGENTS.md`](../AGENTS.md), which are
descriptions of intent rather than rules. Where the two disagree, this document is correct and
`AGENTS.md` is stale.

> **Draft status — read before implementing.** Three things below are decided; one is not.
>
> | Item | Status |
> |---|---|
> | Rotation determines the next round's opener | Decided |
> | No open-ended series mode; a strike limit is required | Decided — revisit only on playtest evidence of demand |
> | Ranking: shared rank on equal strikes, elimination order where elimination applies | Decided |
> | **Mid-match withdrawal** | **Open.** [`withdraw`](#the-unspecified-operation) is named and unspecified |
>
> Everything else marked **[draft default]** is a choice made in writing this document, not a product
> decision. Those are the lines to argue with.

---

## Scope: the match, not the round and not the session

**The match layer** consumes a sequence of round results and produces standings and a match outcome.
It charges strikes, eliminates or ends on a strike limit, chooses each round's opener and roster, and
seeds the round engine's cross-round exclusion sets.

**It is not the round engine.** It never sees a `Move`, never touches `castIds`, and has no opinion
about whether a chain is valid. It receives a `RoundOver` and treats it as fact.

**It is not the session layer.** It has no clock, no store, no transport, and no graph.

### Where the seam falls

The round/match seam is drawn by constitutive vs. regulative
([ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md#where-the-seam-falls)). That test does not extend
upward, so the match/session seam needs its own:

> **The match layer owns what is derivable from the sequence of round results. The session layer owns
> what requires a clock, the graph, durable storage, or a network peer.**

The test resolves the cases that look ambiguous. Detecting that a player has abandoned a match needs a
clock — session. What that abandonment does to standings is a function of the result sequence — match.
Adjudicating a lapsed deadline is session; that the resulting `RoundOver` costs a strike is match.

### Configuration vs. arguments

A match carries settings the match layer never reads — `turn_duration` most obviously, which is
session-layer configuration fixed at match start. Those live in the match's persisted configuration
record. They are **not** parameters of the functions below, and adding them there is the beginning of
the pure layer growing an I/O layer's concerns.

`MatchConfig` in this document means only what the match layer's rules consume.

---

## How to use this document

**To implement a match layer:** satisfy every rule in [Rules](#rules). The
[conformance suite](#conformance-suite) generates a test suite in any language; the
[outcome table](#the-outcome-table) covers the configuration space and the numbered cases cover the
sequential properties a table cannot express.

**To change match behavior:** change this document first. A rule and its cases move together.

**Rules are numbered M1–M15** so they never collide with the engine's R1–R17. Cases are MC-nn.

---

## Vocabulary

| Term | Meaning |
|---|---|
| **Match** | A series of rounds among a fixed set of players, ending in standings |
| **Round** | One chain, built and adjudicated by the round engine; produces exactly one `RoundOver` |
| **Strike** | The cost of losing a round. Lowest total is best |
| **PlayerId** | A stable identity for a player, constant for the life of the match |
| **SeatIndex** | A position in one round's roster. **Round-local** — see [M9](#m9--a-seat-index-is-round-local) |
| **Match order** | The fixed ordering of all players, set at match start and never changed ([M2](#m2--the-match-order-is-fixed)) |
| **Active** | A player still in play: not eliminated, not withdrawn |
| **Roster** | The ordered list of active players handed to one round, opener first |

---

## Data model

```
PlayerId = opaque, equatable, stable for the life of the match

MatchConfig:
    strikeLimit:   Int              # >= 1
    onLimit:       LimitPolicy
    reuse:         ReusePolicy

LimitPolicy = Eliminate | EndMatch
ReusePolicy = Allowed | Forbidden

MatchInProgress:
    config:            MatchConfig
    matchOrder:        List<PlayerId>   # fixed; >= 2 entries; all distinct
    strikes:           Map<PlayerId, Int>
    eliminated:        List<PlayerId>    # in elimination order; empty under EndMatch
    nextOpener:        PlayerId          # always an active player
    roundsPlayed:      Int               # the index of the next round to be played
    excludedActorIds:  Set<EntityId>     # empty unless reuse == Forbidden
    excludedMovieIds:  Set<EntityId>     # empty unless reuse == Forbidden

MatchOver:
    config:            MatchConfig
    matchOrder:        List<PlayerId>
    strikes:           Map<PlayerId, Int>
    eliminated:        List<PlayerId>
    roundsPlayed:      Int

MatchState   = MatchInProgress | MatchOver
MatchOutcome = MatchInProgress | MatchOver
```

**`MatchOver` carries no winner field**, for the same reason `RoundOver` carries no winner
([ENGINE_CONFORMANCE.md R8](ENGINE_CONFORMANCE.md#r8--loser-determination)): it is derivable, and it is
not total. Under `Eliminate` exactly one player survives and "winner" is unambiguous; under `EndMatch`
first place can be shared. A field that is meaningful under one policy and multi-valued under the other
is a projection, not state — see [M10](#m10--standings).

**`eliminated` is a list, not a set.** Its order is load-bearing: it is the only thing that
distinguishes two players who were both eliminated at exactly the strike limit
([M10](#m10--standings)).

**`matchOrder` retains eliminated and withdrawn players.** See [M2](#m2--the-match-order-is-fixed) for
why, and what it costs to do otherwise.

**There is no `MatchOutcome` variant for a rejected or ignored round result.** A round result is either
applied or the call is malformed ([M14](#m14--malformed-input-is-an-error-never-a-match-outcome)).

### What this layer receives

From [`ENGINE_CONFORMANCE.md`](ENGINE_CONFORMANCE.md#data-model), unchanged:

```
RoundOver:
    loserIndex:   Int                  # a SeatIndex into that round's roster
    chain:        List<Move>           # accepted moves; EXCLUDES the losing move
    losingMove:   Move?
    reason:       RoundEndReason       # Unconnected | GaveUp | DeadlineLapsed
```

**Nothing in this document requires a change to the engine spec or to `RoundOver`.** The round index
needed for duplicate detection is held by the match layer and passed as an argument
([M15](#m15--a-round-result-applies-once)), not added as a field the engine has no way to populate.

---

## Operations

```
applyRoundResult(match: MatchInProgress, roundIndex: Int, result: RoundOver) -> MatchOutcome

nextRound(match: MatchInProgress) -> RoundSetup
standings(match: MatchState)      -> List<Standing>

RoundSetup:
    roster:            List<PlayerId>  # opener at index 0
    playerCount:       Int             # == roster.size
    excludedActorIds:  Set<EntityId>
    excludedMovieIds:  Set<EntityId>

Standing:
    player:  PlayerId
    rank:    Int          # 1-based; may be shared
    strikes: Int
    status:  Active | Eliminated
```

All three are pure functions of their arguments. None performs I/O. None mutates its input
([M13](#m13--the-match-layer-is-pure)).

`nextRound` and `standings` are **projections** — derived from `MatchInProgress`, never stored
alongside it. Storing a projection is how a match acquires two sources of truth for the same fact.

`RoundSetup` is exactly the round engine's construction arguments. The match layer produces it; the
session layer passes it to the engine and persists the resulting round state.

### The unspecified operation

```
withdraw(match: MatchInProgress, player: PlayerId) -> MatchOutcome    # UNSPECIFIED
```

Named here because its absence is load-bearing, not because its behavior is decided.

**Why it cannot be omitted.** With the open-ended series dropped, every match reaches a terminal state
within `strikeLimit × |matchOrder|` rounds ([M12](#m12--every-match-terminates)) *provided rounds keep
completing*. Withdrawal and stalling are the only two ways that premise fails. Stalling is a session
concern — a match with a defined finish line that nobody is walking toward, resolvable by a deadline
policy. Withdrawal is not: a player who has left will not lose rounds, so the match cannot progress
toward its limit at all.

**The sub-question that decides the shape.** At N = 2 there is no "continue with the remaining
players." Withdrawal there is either a match forfeit — the withdrawer takes a terminal placement — or
the match voids and produces no standings. Whichever is chosen, N > 2 should follow the same principle
rather than being specified separately; a rule that treats two players as a special case is a second
rule.

**What is already fixed regardless of the answer.** A withdrawn player keeps their position in
`matchOrder`, so opener rotation is unaffected ([M2](#m2--the-match-order-is-fixed),
[M7](#m7--the-next-opener-is-the-next-active-player-in-match-order)), and rotation skips them exactly as
it skips an eliminated player. The structure is ready; only the policy is missing.

---

## Rules

### M1 — Match configuration is fixed at match start

`MatchConfig` is chosen before the first round and never changes. No operation in this document
modifies it.

`strikeLimit >= 1`. There is no unlimited value and no "no limit" mode: an unbounded series has no
terminal state derivable from round results, which makes `MatchOver` unreachable, standings a running
projection rather than a result, and every match a permanently live row with a permanently pending turn.
It is dropped as a mode and revisited only on playtest evidence that players want it.

### M2 — The match order is fixed

`matchOrder` is set at match start, contains every player exactly once, and **never changes**. Players
who are eliminated or withdrawn keep their positions; they are skipped, not removed
([M7](#m7--the-next-opener-is-the-next-active-player-in-match-order)).

Who occupies `matchOrder[0]` is a session-layer decision — creation order, invitation order, or a
shuffle. The match layer receives the order and does not choose it.

**A shrinking ordered list of active players produces the same opener sequence** and is not wrong. It
costs three things. Eliminated players stay in the match record for standings regardless, so nothing is
saved — a shrinking list plus an elimination log holds what one fixed list plus a strike table already
holds. Per-round rosters stop being derivable, so interpreting a stored `RoundOver.loserIndex` from an
earlier round requires having snapshotted that round's roster. And it is correct only when removal and
the opener advance happen as one operation: if the player being removed is `nextOpener`, the advance
must be computed before the removal. That coupling holds at every removal site, including asynchronous
withdrawal, and nothing enforces it. A fixed order has no such invariant.

### M3 — A round loss costs exactly one strike

`applyRoundResult` charges one strike to the round's loser and to no one else. No other event in this
document charges a strike.

```
loser = nextRound(match).roster[result.loserIndex]
strikes[loser] += 1
```

The loser is resolved through **the roster of the round being applied**, never through `matchOrder`
([M9](#m9--a-seat-index-is-round-local)).

### M4 — The strike does not depend on the round-end reason **[draft default]**

`Unconnected`, `GaveUp`, and `DeadlineLapsed` all cost one strike.

This is the simplest reading and the only one anyone has stated, but it is a default rather than a
settled position. [`ENGINE_CONFORMANCE.md`](ENGINE_CONFORMANCE.md#data-model) justifies the existence of
`RoundOver.reason` on the grounds that "the match layer charges penalties, and the penalties differ" —
it asserts a differential without specifying one, and this document does not invent it. `reason` is
the seam for a differential penalty table if one is ever wanted. See [Open questions](#open-questions).

`reason` has a second use that does not depend on that question: repeated `DeadlineLapsed` from the
same player is the signal that they have stopped playing, which is the evidence any withdrawal or
abandonment policy will be built on.

### M5 — Elimination

Under `onLimit == Eliminate`, a player whose strike total reaches `strikeLimit` is appended to
`eliminated` and ceases to be active. Their strike total is frozen — they lose no further rounds.

Under `onLimit == EndMatch`, no player is ever eliminated and `eliminated` stays empty.

**At most one player is eliminated per round**, because a round has exactly one loser and charges
exactly one strike. Elimination order is therefore a total order, which is what makes
[M10](#m10--standings) well-defined.

### M6 — Match end

```
Eliminate:  the match ends when exactly one active player remains
EndMatch:   the match ends when any player's strike total reaches strikeLimit
```

`applyRoundResult` returns `MatchOver` on the transition and `MatchInProgress` otherwise.

**At N = 2 the two policies coincide.** Eliminating one of two players leaves one active player, which
ends the match; and that player reached the limit, which also ends the match. Same outcome, same round.
An implementation that special-cases either policy at N = 2 is wrong even if it agrees here
([MC-05](#mc-05--the-two-limit-policies-coincide-in-a-two-player-match)).

### M7 — The next opener is the next active player in match order

```
nextOpener' = the first active player strictly after nextOpener in matchOrder, cyclically
```

Rotation, not compensation: the opener advances by one active position after every round regardless of
who lost. The opener cannot fail their move — an empty chain skips the connection and type checks
([ENGINE_CONFORMANCE.md R1](ENGINE_CONFORMANCE.md#r1--the-opening-move-is-not-connection-checked)) — so
the position carries a small structural advantage, and rotation distributes it evenly.

The scan is over `matchOrder`, so it is well-defined when `nextOpener` was themselves eliminated by the
round just applied: they still hold their position, and the scan starts strictly after it.

**Order of evaluation within `applyRoundResult`:** charge the strike, apply elimination, then advance
the opener. Advancing first can select a player who is eliminated microseconds later.

### M8 — The round roster is derived, never stored

```
roster = matchOrder filtered to active players, rotated so nextOpener is at index 0
```

`playerCount == roster.size`, which the engine requires to be `>= 2`. Under `Eliminate` the match ends
at one active player ([M6](#m6--match-end)), so no round is ever constructed below that floor.

Play order within a round is `matchOrder` cyclically — the roster *is* the play order. There is not a
separate turn order and opener rule to keep consistent.

### M9 — A seat index is round-local

`RoundOver.loserIndex` is a position in the roster of **the round that produced it** and has no meaning
outside it. Under `Eliminate` the roster shrinks and rotates between rounds, so the same index names
different players in different rounds.

A match layer that resolves `loserIndex` against `matchOrder`, or against the current roster when
applying a stored result from an earlier round, charges strikes to the wrong player. This is the
failure mode the `PlayerId` / `SeatIndex` distinction exists to prevent, and
[MC-10](#mc-10--a-seat-index-does-not-survive-a-roster-change) pins it.

**Interpreting a stored round result requires that round's roster.** It is derivable from
`matchOrder`, the elimination history, and the round index — which is what
[M2](#m2--the-match-order-is-fixed) buys.

### M10 — Standings

```
1. Active players rank above all eliminated players.
2. Active players are ordered by strike total, ascending.
3. Equal strike totals share a rank.
4. Eliminated players are ordered by elimination order, descending — last eliminated ranks higher.
```

Shared ranks use **standard competition ranking**: the next distinct rank skips by the size of the tie
group (1, 2, 2, 4). **[draft default]** — a presentation convention, cheap to change.

**Why elimination order and not strikes.** Every eliminated player has exactly `strikeLimit` strikes;
that is the definition of being eliminated. Ranking them by strike total ties all of them for last,
which erases the difference between a player eliminated in round 7 and one who survived to round 20.
Lowest-strikes-wins is a total order under `EndMatch` and an incomplete one under `Eliminate`.

`standings` is defined for `MatchInProgress` and `MatchOver` alike; mid-match it is a running view.

**Final standings under `Eliminate` contain no ties**: exactly one player is active, and the rest are
totally ordered by elimination. Under `EndMatch`, first place may be shared.

### M11 — Cross-round exclusions accumulate under hard mode

Under `reuse == Forbidden`, after each round the entities of `result.chain` are unioned into
`excludedActorIds` / `excludedMovieIds` by type, and `nextRound` passes them to the engine.

Under `reuse == Allowed` both sets stay empty and are passed empty. This is the default mode: a new
round makes every entity available again.

**`result.losingMove` is not excluded.** It was never accepted into the chain — `RoundOver` separates
the two fields precisely so this distinction is expressible — so it was never played, and banning it
would punish a guess.

The sets grow monotonically across rounds, so match state under hard mode grows with entities played.
Note also that [ADR 019](DECISIONS.md) measured exhausted-frontier risk as rare under **empty**
exclusion sets; that measurement does not transfer to a mode that thins the frontier every round. It is
unmeasured, not known to be a problem.

### M12 — Every match terminates

Given that rounds keep completing, a match ends within `strikeLimit × |matchOrder|` rounds under either
policy.

Each round charges exactly one strike ([M3](#m3--a-round-loss-costs-exactly-one-strike)). Under
`EndMatch` the match ends once any player reaches `L`, so at most `N(L−1) + 1` rounds are played. Under
`Eliminate` it ends when one player remains: `N−1` players at `L` strikes each plus a survivor with at
most `L−1` is at most `LN − 1` strikes, hence at most that many rounds.

**Termination is joint, exactly as it is at the round layer**
([ENGINE_CONFORMANCE.md R17](ENGINE_CONFORMANCE.md#r17--every-round-terminates)). The match layer bounds
the match given that rounds complete. It does not bound a match where nobody moves — that is the session
layer's deadline, one level up from the retry loop R17 delegates.

Unlike R17's ~95,000-move chain bound, `L × N` is small enough to plan persistence and payload sizes
against.

### M13 — The match layer is pure

`applyRoundResult`, `nextRound`, and `standings` are pure functions: no I/O, no clock, no randomness, no
graph access, no mutation of arguments. Called twice with equal arguments they return equal results.

The consequences are the engine's, one layer up. Randomness — a shuffled opening `matchOrder` — is
resolved by the session layer before the match exists, and arrives as data.

### M14 — Malformed input is an error, never a match outcome

These are caller defects and must raise, not resolve to a `MatchOutcome`:

- `applyRoundResult` on a `MatchOver` — no operation applies to a terminal state
- `roundIndex != match.roundsPlayed` ([M15](#m15--a-round-result-applies-once))
- `result.loserIndex` out of range for the round's roster
- `strikeLimit < 1`, `matchOrder` shorter than 2 entries, or containing duplicates
- `nextOpener` not an active player

Returning any of these as an outcome hides a bug behind a plausible-looking standings table. The engine
spec's rationale applies unchanged
([R15](ENGINE_CONFORMANCE.md#r15--malformed-input-is-an-error-never-a-round-outcome)).

### M15 — A round result applies once

`roundIndex` must equal `match.roundsPlayed`; `applyRoundResult` increments it. A stale index raises
([M14](#m14--malformed-input-is-an-error-never-a-match-outcome)).

Without it, applying the same `RoundOver` twice double-charges a strike, and a pure function cannot
detect the duplicate on its own — `RoundOver` carries no identity, and two rounds can legitimately
produce identical results.

**This is detection, not idempotent replay.** The pure layer refuses the stale call; the session layer
maps that refusal onto the stored outcome for the round in question, which is where the
compare-and-swap and any client-supplied move ID already live ([AGENTS.md](../AGENTS.md), *Deployment*).

---

## Match boundary

Required by the product, enforced elsewhere. A match layer that enforces these is over-scoped.

| Concern | Enforced by |
|---|---|
| Whether a chain is valid; who lost a round | Round engine |
| Choosing `matchOrder[0]`, or shuffling the order | Session layer, before the match exists ([M13](#m13--the-match-layer-is-pure)) |
| Detecting a lapsed deadline, and calling `forfeit` | Session layer ([ENGINE_CONFORMANCE.md R7](ENGINE_CONFORMANCE.md#r7--forfeit-ends-the-round)) |
| Detecting abandonment or a stalled match | Session layer; it holds the clock ([M12](#m12--every-match-terminates)) |
| `turn_duration` and `deadline_at` | Session layer; not in `MatchConfig` |
| Persisting match state; compare-and-swap on a version | Session layer |
| Mapping a duplicate submission onto the stored outcome | Session layer ([M15](#m15--a-round-result-applies-once)) |
| Invitations, joining, matchmaking | Out of scope for the product ([AGENTS.md](../AGENTS.md)) |
| Presenting standings; naming a "winner" from rank 1 | Client |

---

## Conformance suite

Fixtures. Four players, distinct and stable:

```
P0, P1, P2, P3      # PlayerIds
matchOrder = [P0, P1, P2, P3]

ELIM_3   = MatchConfig(strikeLimit=3, onLimit=Eliminate, reuse=Allowed)
END_3    = MatchConfig(strikeLimit=3, onLimit=EndMatch,  reuse=Allowed)
HARD_3   = MatchConfig(strikeLimit=3, onLimit=Eliminate, reuse=Forbidden)
```

A round result naming seat `i`, with a chain, is written `loss(i)`. Unless a case says otherwise the
reason is `Unconnected` and the chain is irrelevant to the assertion.

**Two properties hold across the suite; preserve both when translating.**

*Every GIVEN match state is legally reachable* — reachable by applying some sequence of round results
from a fresh match under the stated config. A case asserting behavior from an unreachable state proves
nothing.

*Each case isolates one rule.* Where a state could trigger more than one transition, the fixtures are
chosen so exactly one applies. [MC-05](#mc-05--the-two-limit-policies-coincide-in-a-two-player-match) and
[MC-10](#mc-10--a-seat-index-does-not-survive-a-roster-change) are the exceptions; stacking is what they
exist to pin.

### The outcome table

One strike is charged in every row ([M3](#m3--a-round-loss-costs-exactly-one-strike)). The table covers
`applyRoundResult`'s configuration space; the numbered cases cover what a table cannot express.

| # | Policy | Loser's strikes before | Active players | Outcome |
|---|---|---|---|---|
| MC-01 | either | 0 | 4 | `MatchInProgress`; strikes 1; no elimination |
| MC-02 | `EndMatch` | 2 (limit 3) | 4 | `MatchOver`; loser has 3; `eliminated` empty |
| MC-03 | `Eliminate` | 2 (limit 3) | 4 | `MatchInProgress`; loser appended to `eliminated`; 3 active |
| MC-04 | `Eliminate` | 2 (limit 3) | 2 | `MatchOver`; loser eliminated; one active remains |
| MC-20 | either | 0 | 4 | Same as MC-01 for each `RoundEndReason` — see below |

### Group A — Strikes and match end

#### MC-01 — A round loss charges one strike to the round's loser

GIVEN a fresh match, `ELIM_3`, all strikes 0, `nextOpener = P0`, `roundsPlayed = 0`
WHEN `applyRoundResult(match, 0, loss(2))`
THEN `MatchInProgress`; `strikes = {P0:0, P1:0, P2:1, P3:0}`; `eliminated` empty; `roundsPlayed = 1`

Seat 2 of roster `[P0, P1, P2, P3]` is P2. No other player's total changes.

#### MC-02 — Reaching the limit under EndMatch ends the match

GIVEN `END_3`, `strikes = {P0:0, P1:2, P2:1, P3:0}`, `nextOpener = P0`
WHEN a result naming P1 is applied
THEN `MatchOver`; `strikes[P1] == 3`; `eliminated` is empty

`EndMatch` never eliminates ([M5](#m5--elimination)) — assert the empty list, not just the outcome.

#### MC-03 — Reaching the limit under Eliminate removes the player and continues

GIVEN `ELIM_3`, `strikes = {P0:0, P1:2, P2:1, P3:0}`, `nextOpener = P0`
WHEN a result naming P1 is applied
THEN `MatchInProgress`; `eliminated == [P1]`; active is `{P0, P2, P3}`; `nextRound().playerCount == 3`

#### MC-04 — The last elimination ends the match

GIVEN `ELIM_3`, `eliminated == [P1, P3]`, `strikes = {P0:1, P1:3, P2:2, P3:3}`, `nextOpener = P0`
WHEN a result naming P2 is applied
THEN `MatchOver`; `eliminated == [P1, P3, P2]`; P0 is the only active player

The match ends because one active player remains ([M6](#m6--match-end)) — not because a count of
eliminations was reached.

#### MC-05 — The two limit policies coincide in a two-player match

GIVEN two matches over `matchOrder = [P0, P1]`, identical but for `onLimit`, `strikes = {P0:0, P1:2}`,
limit 3
WHEN a result naming P1 is applied to each
THEN both return `MatchOver` with `strikes[P1] == 3`, and `standings` ranks P0 first in both

The two differ only in `eliminated`: `[P1]` under `Eliminate`, empty under `EndMatch`. Rank is
unaffected, which is the point — [M10](#m10--standings) rule 1 is vacuous when there is one active
player and one eliminated player.

#### MC-20 — The round-end reason does not change the strike

GIVEN three identical fresh `ELIM_3` matches
WHEN a result naming seat 2 is applied to each, with `reason` of `Unconnected`, `GaveUp`, and
`DeadlineLapsed` respectively
THEN all three return equal `MatchInProgress` values

Pins [M4](#m4--the-strike-does-not-depend-on-the-round-end-reason-draft-default). If a differential
penalty table is ever adopted, this is the case that changes.

### Group B — Rotation and rosters

#### MC-06 — The opener rotates by one active position per round

GIVEN `ELIM_3`, no eliminations, `nextOpener = P0`
WHEN four results are applied in sequence
THEN `nextOpener` is P1, P2, P3, P0 after each

Rotation is independent of who lost: assert this with the same seat losing every round.

#### MC-07 — Rotation skips an eliminated player

GIVEN `ELIM_3`, `eliminated == [P2]`, `nextOpener = P1`
WHEN a result is applied that eliminates nobody
THEN `nextOpener == P3`

P2 holds their position in `matchOrder` and is skipped, not removed
([M2](#m2--the-match-order-is-fixed)).

#### MC-08 — Rotation is well-defined when the opener is eliminated by the round just applied

GIVEN `ELIM_3`, `strikes = {P0:0, P1:2, P2:0, P3:0}`, `nextOpener = P1`, no prior eliminations
WHEN a result naming P1 is applied
THEN `MatchInProgress`; `eliminated == [P1]`; `nextOpener == P2`

The scan starts strictly after P1's position in `matchOrder`, which P1 still occupies. An
implementation that removes the player before advancing has no position to scan from.

This case is why [M7](#m7--the-next-opener-is-the-next-active-player-in-match-order) fixes the order of
evaluation. Its mirror also holds: advancing before eliminating would make `nextOpener` P2 here as
well, but selects an eliminated player whenever the *next* player is the one eliminated — construct
that variant if the implementation evaluates in a different order.

#### MC-09 — The roster is match order, filtered and rotated

GIVEN `ELIM_3`, `eliminated == [P1]`, `nextOpener = P2`
THEN `nextRound().roster == [P2, P3, P0]` and `playerCount == 3`

Opener at index 0; the rest follow `matchOrder` cyclically.

#### MC-10 — A seat index does not survive a roster change

GIVEN `ELIM_3`, `eliminated == [P1]`, `nextOpener = P2`, so `roster == [P2, P3, P0]`
WHEN `loss(1)` is applied
THEN `strikes[P3]` increases, and `strikes[P1]` does not

Seat 1 is P3 in this round and was P1 in the opening round. A match layer resolving `loserIndex`
against `matchOrder` charges P1 — a player who is not even in the round
([M9](#m9--a-seat-index-is-round-local)). This is the highest-value case in the suite; an
implementation that passes everything else and fails this one silently corrupts every match that
reaches an elimination.

### Group C — Standings

#### MC-11 — Active players outrank eliminated players regardless of strikes

GIVEN `ELIM_3`, `strikes = {P0:2, P1:3, P2:0, P3:1}`, `eliminated == [P1]`
THEN `standings` ranks P2 (0), P3 (1), P0 (2), then P1

P0 has two strikes and P1 has three, so strike order and rank agree here by accident; construct the
variant with `strikeLimit = 1` and `strikes = {P0:0, P1:1}` where an eliminated player has *fewer*
strikes than nobody — and confirm the partition is applied before the sort, not as a tiebreak.

#### MC-12 — Equal strike totals share a rank

GIVEN `END_3`, `strikes = {P0:1, P1:1, P2:0, P3:2}`
THEN ranks are P2 = 1, P0 = 2, P1 = 2, P3 = 4

Standard competition ranking: the tie group of two consumes ranks 2 and 3, and the next distinct rank
is 4. **[draft default]** — a dense-ranking implementation (1, 2, 2, 3) fails this case and is a
one-line change if preferred.

#### MC-13 — Eliminated players rank in reverse elimination order

GIVEN `ELIM_3` at `MatchOver`, `eliminated == [P1, P3, P2]`, `strikes = {P0:1, P1:3, P2:3, P3:3}`
THEN ranks are P0 = 1, P2 = 2, P3 = 3, P1 = 4, with no shared ranks

All three eliminated players have exactly `strikeLimit` strikes. Ranking them by strike total ties them
for second; only elimination order separates them, and later elimination ranks higher
([M10](#m10--standings)).

#### MC-14 — Final standings under Eliminate contain no ties

GIVEN any `MatchOver` produced under `Eliminate`
THEN every rank in `standings` is distinct

A structural property, not a fixture: one active player, and eliminations are totally ordered because a
round has one loser ([M5](#m5--elimination)). Assert it as a property over generated matches if the
language makes that cheap.

### Group D — Exclusions

#### MC-15 — Hard mode accumulates the chain across rounds

GIVEN `HARD_3`, empty exclusion sets
WHEN a result is applied whose `chain` is `[Actor(Q1), Movie(Q10), Actor(Q2)]`
THEN `excludedActorIds == {Q1, Q2}`, `excludedMovieIds == {Q10}`, and `nextRound()` passes both

#### MC-16 — The losing move is not excluded

GIVEN `HARD_3`, empty exclusion sets
WHEN a result is applied with `chain == [Actor(Q1), Movie(Q10)]` and `losingMove == Actor(Q7)`
THEN `excludedActorIds == {Q1}` — Q7 is absent

Q7 was never accepted into the chain ([M11](#m11--cross-round-exclusions-accumulate-under-hard-mode)).

#### MC-17 — The default mode excludes nothing

GIVEN `ELIM_3` (`reuse == Allowed`)
WHEN any result with a non-empty chain is applied
THEN both exclusion sets remain empty, and `nextRound()` passes empty sets

### Group E — Purity and input validation

#### MC-18 — Applying a result twice is an error

GIVEN any `MatchInProgress` with `roundsPlayed == n`
WHEN `applyRoundResult(match, n, result)` succeeds and `applyRoundResult(match, n, result)` is called
again on the **original** match value
THEN the second call raises ([M15](#m15--a-round-result-applies-once))

Also assert the first call left the original `match` value unmutated
([M13](#m13--the-match-layer-is-pure)) — the two assertions together are what make the operation safe
to retry at the session layer.

#### MC-19 — No operation applies to a terminal match

GIVEN any `MatchOver`
WHEN `applyRoundResult` is called
THEN it raises ([M14](#m14--malformed-input-is-an-error-never-a-match-outcome))

`standings` remains callable on `MatchOver` — that is its final form.

#### MC-21 — An out-of-range seat index is an error

GIVEN `ELIM_3`, `eliminated == [P1]`, so `playerCount == 3`
WHEN a result with `loserIndex == 3` is applied
THEN it raises

Valid against the four-player opening roster, invalid here. A match layer that resolves against
`matchOrder` accepts it and charges the wrong player, which is [MC-10](#mc-10--a-seat-index-does-not-survive-a-roster-change)
in its silent form.

#### MC-22 — Match construction is validated

Each of these raises at construction: `strikeLimit == 0`; `matchOrder` with one entry; `matchOrder`
containing a duplicate `PlayerId`; `nextOpener` not present in `matchOrder`.

---

## Open questions

**Mid-match withdrawal.** The one operation named and unspecified; see
[The unspecified operation](#the-unspecified-operation). It determines whether
[M12](#m12--every-match-terminates) is a rule or an aspiration, and its N = 2 answer should set the
shape for N > 2.

**Whether penalties differ by round-end reason.**
[M4](#m4--the-strike-does-not-depend-on-the-round-end-reason-draft-default) charges one strike
uniformly. [`ENGINE_CONFORMANCE.md`](ENGINE_CONFORMANCE.md#data-model) asserts that penalties differ
when justifying `RoundOver.reason`, without saying how. Either this document adopts a differential and
[MC-20](#mc-20--the-round-end-reason-does-not-change-the-strike) changes, or the engine spec's rationale
is narrowed to the uses that survive — abandonment detection, and presentation.

**Whether hard mode needs a frontier guard.** [M11](#m11--cross-round-exclusions-accumulate-under-hard-mode)
accumulates exclusions monotonically, thinning the graph frontier every round. [ADR 019](DECISIONS.md)
measured exhausted-frontier risk as rare under empty exclusion sets; that result does not transfer.
Unmeasured, and not blocking — hard mode is not the default.

**Where a match's terminal state goes.** [M12](#m12--every-match-terminates) makes every match
terminal, so terminal matches can be archived or compacted out of the hot path. Whether they are is a
storage-selection input, not a rule here — it is the one requirement this layer places on
[agenda §3.2](PLANNING_AGENDA.md).

**Rematch and series.** Whether finishing a match can seed a new one with the same roster is
unspecified and out of scope for this document; it would be a new match, not a match-layer state.

---

## Related documents

| Document | Relationship |
|---|---|
| [ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md) | The layer below. Produces the `RoundOver` this document consumes; its [Engine boundary](ENGINE_CONFORMANCE.md#engine-boundary) table delegates to this document |
| [DECISIONS.md](DECISIONS.md) | [ADR 021](DECISIONS.md) established the round outcome taxonomy this layer reads; [ADR 012](DECISIONS.md)/[018](DECISIONS.md) the deadline model the session layer owns |
| [AGENTS.md](../AGENTS.md) | Operating rules. Its match-layer summaries are superseded by this document and need reconciling once it is accepted |
| [PLANNING_AGENDA.md](PLANNING_AGENDA.md) | §4.1 is this document's commissioning entry |
