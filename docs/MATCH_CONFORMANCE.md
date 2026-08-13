# Bacon's Law — Match Layer Conformance Spec

**Status:** DRAFT. Authoritative for match-layer behavior once accepted. Language- and
framework-agnostic.

This document specifies the layer above the round engine: what a round loss costs, when a match ends,
who opens each round, and how players are ranked. It is the other half of the seam that
[`ENGINE_CONFORMANCE.md`](ENGINE_CONFORMANCE.md) stops at.

It takes precedence over the match-layer summaries in [`AGENTS.md`](../AGENTS.md), which are
descriptions of intent rather than rules. Where the two disagree, this document is correct and
`AGENTS.md` is stale.

> **Draft status — read before implementing.**
>
> | Item | Status |
> |---|---|
> | Rotation determines the next round's opener | Decided |
> | No open-ended series mode; a strike limit is required | Decided — revisit only on playtest evidence of demand |
> | Ranking: shared rank on equal strikes, removal order where players have been removed | Decided |
> | A lapsed deadline removes the player from the match | Decided — see [M4](#m4--the-round-end-reason-determines-removal) |
> | Withdrawal and a lapse are the same removal | Decided — see [M16](#m16--withdrawal) |
>
> Lines marked **[draft default]** are choices made in writing this document rather than product
> decisions. There is one, in [M10](#m10--standings).

---

## Scope: the match, not the round and not the session

**The match layer** consumes a sequence of round results and produces standings and a match outcome.
It charges strikes, removes players, chooses each round's opener and roster, and seeds the round
engine's cross-round exclusion sets.

**It is not the round engine.** It never sees a `Move`, never touches `castIds`, and has no opinion
about whether a chain is valid. It receives a `RoundOver` and treats it as fact.

**It is not the session layer.** It has no clock, no store, no transport, and no graph. In particular
it does not detect a lapsed deadline — it is told one happened, by a `RoundOver` carrying
`DeadlineLapsed`.

### Where the seam falls

The round/match seam is drawn by constitutive vs. regulative
([ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md#where-the-seam-falls)). That test does not extend
upward, so the match/session seam needs its own:

> **The match layer owns what is derivable from the sequence of round results. The session layer owns
> what requires a clock, the graph, durable storage, or a network peer.**

The test resolves the cases that look ambiguous. Detecting that a deadline lapsed needs a clock and is
session; that a lapse removes the player is derivable from the result and is match. Deciding when to
declare a match abandoned is session; what abandonment does to standings is match.

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

**Rules are numbered M1–M16** so they never collide with the engine's R1–R17. Cases are MC-nn.

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
| **Active** | A player still in play: not removed |
| **Removed** | A player out of the match, by strike limit, lapsed deadline, or withdrawal ([M5](#m5--removal-from-play)) |
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

Removal:
    player:  PlayerId
    cause:   RemovalCause

RemovalCause = StrikeLimit | Lapsed | Withdrew

MatchInProgress:
    config:            MatchConfig
    matchOrder:        List<PlayerId>   # fixed; >= 2 entries; all distinct
    strikes:           Map<PlayerId, Int>
    removed:           List<Removal>     # in removal order
    nextOpener:        PlayerId          # always an active player
    roundsPlayed:      Int               # the index of the next round to be played
    excludedActorIds:  Set<EntityId>     # empty unless reuse == Forbidden
    excludedMovieIds:  Set<EntityId>     # empty unless reuse == Forbidden

MatchOver:
    config:            MatchConfig
    matchOrder:        List<PlayerId>
    strikes:           Map<PlayerId, Int>
    removed:           List<Removal>
    roundsPlayed:      Int

MatchState   = MatchInProgress | MatchOver
MatchOutcome = MatchInProgress | MatchOver
```

**`MatchOver` carries no winner field**, for the same reason `RoundOver` carries no winner
([ENGINE_CONFORMANCE.md R8](ENGINE_CONFORMANCE.md#r8--loser-determination)): it is derivable, and it is
not total. A match that ends with one active player has an unambiguous winner; a match that ends on the
strike limit under `EndMatch` can have several players sharing first. A field that is single-valued in
one case and multi-valued in the other is a projection, not state — see [M10](#m10--standings).

**`removed` is an ordered list, not a set.** Its order is load-bearing: it is the only thing that
distinguishes two players who left at the same strike total ([M10](#m10--standings)). It carries the
cause because standings display it, not because ranking depends on it — ranking uses order alone.

**`matchOrder` retains removed players.** See [M2](#m2--the-match-order-is-fixed) for why, and what it
costs to do otherwise.

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

**Nothing in this document requires a change to the engine spec or to `RoundOver`.** `reason` is the
entire seam by which a lapse becomes a match-level consequence, and the engine already anticipated the
shape: it specifies that `forfeit` "concedes the round, not the match — a player quitting the match
outright is a match-layer event that happens to end the current round this way"
([R7](ENGINE_CONFORMANCE.md#r7--forfeit-ends-the-round)).

The round index needed for duplicate detection is held by the match layer and passed as an argument
([M15](#m15--a-round-result-applies-once)), not added as a field the engine has no way to populate.

---

## Operations

```
applyRoundResult(match: MatchInProgress, roundIndex: Int, result: RoundOver) -> MatchOutcome
withdraw(match: MatchInProgress, player: PlayerId)                           -> MatchOutcome

nextRound(match: MatchInProgress) -> RoundSetup
standings(match: MatchState)      -> List<Standing>

RoundSetup:
    roster:            List<PlayerId>  # opener at index 0
    playerCount:       Int             # == roster.size
    excludedActorIds:  Set<EntityId>
    excludedMovieIds:  Set<EntityId>

Standing:
    player:  PlayerId
    rank:    Int              # 1-based; may be shared
    strikes: Int
    status:  Active | Removed
    cause:   RemovalCause?    # null if and only if status == Active
```

All four are pure functions of their arguments. None performs I/O. None mutates its input
([M13](#m13--the-match-layer-is-pure)).

`nextRound` and `standings` are **projections** — derived from match state, never stored alongside it.
Storing a projection is how a match acquires two sources of truth for the same fact.

`RoundSetup` is exactly the round engine's construction arguments. The match layer produces it; the
session layer passes it to the engine and persists the resulting round state.

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

`matchOrder` is set at match start, contains every player exactly once, and **never changes**. Removed
players keep their positions; they are skipped, not deleted
([M7](#m7--the-next-opener-is-the-next-active-player-in-match-order)).

Who occupies `matchOrder[0]` is a session-layer decision — creation order, invitation order, or a
shuffle. The match layer receives the order and does not choose it.

**A shrinking ordered list of active players produces the same opener sequence** and is not wrong. It
costs three things. Removed players stay in the match record for standings regardless, so nothing is
saved — a shrinking list plus a removal log holds what one fixed list plus a strike table already
holds. Per-round rosters stop being derivable, so interpreting a stored `RoundOver.loserIndex` from an
earlier round requires having snapshotted that round's roster. And it is correct only when removal and
the opener advance happen as one operation: if the player being removed is `nextOpener`, the advance
must be computed before the removal. That coupling holds at every removal site, including asynchronous
withdrawal, and nothing enforces it. A fixed order has no such invariant.

### M3 — A round loss costs exactly one strike

`applyRoundResult` charges one strike to the round's loser and to no one else. Every round charges
exactly one strike, with no exceptions and regardless of the round-end reason.

```
loser = nextRound(match).roster[result.loserIndex]
strikes[loser] += 1
```

The loser is resolved through **the roster of the round being applied**, never through `matchOrder`
([M9](#m9--a-seat-index-is-round-local)).

No other event charges a strike. [`withdraw`](#m16--withdrawal) charges none, and a lapse charges one
because it lost a round, not because it removes the player. The invariant that follows —
`sum(strikes) == roundsPlayed` — makes a strike table auditable against a round count; preserve it.

### M4 — The round-end reason determines removal

| `reason` | Strike | Removal |
|---|---|---|
| `Unconnected` | 1 | Only if the total reaches `strikeLimit` under `Eliminate` |
| `GaveUp` | 1 | Only if the total reaches `strikeLimit` under `Eliminate` |
| `DeadlineLapsed` | 1 | **Always**, cause `Lapsed` |

A player who lets a deadline lapse is removed from the match immediately, whatever their strike total
and whichever `LimitPolicy` is in force.

**The line is between playing and not playing.** `GaveUp` is a move: the player is present, cannot find
a connection, and ends the round deliberately at the cost of one strike. `DeadlineLapsed` is the
absence of a move. The engine spec draws the same distinction when it justifies carrying `reason` at
all — a player who lets a three-day deadline lapse "has not made the same choice" as one who taps give
up ([ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md#data-model)).

**Why removal and not a strike.** A player who has stopped responding cannot be removed by strikes
alone without grinding through `strikeLimit` rounds, each of which runs until it reaches them — up to
`playerCount` full turn deadlines per round. At a three-day deadline, a limit of 3, and four players,
that is up to 36 days of three engaged players completing rounds that are guaranteed to end on an
absent fourth. Removal on the first lapse is what makes an abandoned match resolve in one deadline
instead of `strikeLimit × playerCount` of them.

**It also makes withdrawal and abandonment equivalent**, which is the property that keeps either from
being the smarter way to quit. See [M16](#m16--withdrawal).

**The cost this rule accepts.** One missed deadline ends the match for that player, and it does not
distinguish a player who has left from one who was briefly unreachable. That falls on engaged players,
not only on the abandoners it targets. It is accepted because the alternative's failure mode costs
every other player weeks, and because harshness scales with the `turn_duration` those players chose.
See [Open questions](#open-questions) for the revisit trigger.

### M5 — Removal from play

A removed player takes no further turns, appears in no further roster, and accrues no further strikes.
Their strike total freezes at whatever they earned.

Three causes, recorded in `Removal.cause`:

| Cause | Trigger | Applies under |
|---|---|---|
| `StrikeLimit` | Strike total reaches `strikeLimit` | `Eliminate` only |
| `Lapsed` | A `RoundOver` with `reason == DeadlineLapsed` ([M4](#m4--the-round-end-reason-determines-removal)) | Both policies |
| `Withdrew` | [`withdraw`](#m16--withdrawal) | Both policies |

**Only `StrikeLimit` is policy-dependent.** Under `EndMatch` no player is removed by the strike limit —
reaching it ends the match instead ([M6](#m6--match-end)) — but `removed` may still be non-empty there
through the other two causes.

**Removals are totally ordered.** `applyRoundResult` produces at most one per call, because a round has
exactly one loser; `withdraw` produces exactly one. Concurrent calls are serialized by the session
layer's compare-and-swap, so `removed` records the order they were applied in. That total order is what
makes [M10](#m10--standings) well-defined.

### M6 — Match end

```
Either policy:  the match ends when fewer than two active players remain
EndMatch only:  the match ends when any player's strike total reaches strikeLimit
```

`applyRoundResult` and `withdraw` both return `MatchOver` on the transition and `MatchInProgress`
otherwise.

**The first clause is universal and load-bearing.** The round engine requires `playerCount >= 2`
([ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md#data-model)), so a match reduced to one active player can
neither continue nor start another round. Under `Eliminate` that clause is the whole condition. Under
`EndMatch` it is the one that catches a match whose players have lapsed or withdrawn away without
anyone reaching the limit — a state reachable only since [M4](#m4--the-round-end-reason-determines-removal)
made removal independent of strikes.

**At two players the two policies coincide** when the trigger is a strike: removing one of two leaves
one active, which ends the match, and that player reached the limit, which also ends it. Same outcome,
same round. An implementation that special-cases either policy at two players is wrong even where it
agrees ([MC-05](#mc-05--the-two-limit-policies-coincide-in-a-two-player-match)).

### M7 — The next opener is the next active player in match order

```
nextOpener' = the first active player strictly after nextOpener in matchOrder, cyclically
```

Rotation, not compensation: the opener advances by one active position after every round regardless of
who lost. The opener cannot fail their move — an empty chain skips the connection and type checks
([ENGINE_CONFORMANCE.md R1](ENGINE_CONFORMANCE.md#r1--the-opening-move-is-not-connection-checked)) — so
the position carries a small structural advantage, and rotation distributes it evenly.

The scan is over `matchOrder`, so it is well-defined when `nextOpener` was themselves removed by the
operation being applied: they still hold their position, and the scan starts strictly after it.

**Order of evaluation, in both operations that can remove a player:** apply the strike, apply the
removal, then advance the opener. Advancing first can select a player removed microseconds later.

### M8 — The round roster is derived, never stored

```
roster = matchOrder filtered to active players, rotated so nextOpener is at index 0
```

`playerCount == roster.size`, which the engine requires to be `>= 2`. The match ends at fewer than two
active players ([M6](#m6--match-end)), so no round is ever constructed below that floor.

Play order within a round is `matchOrder` cyclically — the roster *is* the play order. There is not a
separate turn order and opener rule to keep consistent.

### M9 — A seat index is round-local

`RoundOver.loserIndex` is a position in the roster of **the round that produced it** and has no meaning
outside it. The roster shrinks and rotates as players are removed, so the same index names different
players in different rounds.

A match layer that resolves `loserIndex` against `matchOrder`, or against the current roster when
applying a stored result from an earlier round, charges strikes to the wrong player. This is the
failure mode the `PlayerId` / `SeatIndex` distinction exists to prevent, and
[MC-10](#mc-10--a-seat-index-does-not-survive-a-roster-change) pins it.

**Interpreting a stored round result requires that round's roster.** It is derivable from
`matchOrder`, the removal history, and the round index — which is what
[M2](#m2--the-match-order-is-fixed) buys.

### M10 — Standings

```
1. Active players rank above all removed players.
2. Active players are ordered by strike total, ascending.
3. Equal strike totals share a rank.
4. Removed players are ordered by removal order, descending — last removed ranks higher.
5. Removal cause never affects rank. It is carried for display only.
```

Shared ranks use **standard competition ranking**: the next distinct rank skips by the size of the tie
group (1, 2, 2, 4). **[draft default]** — a presentation convention, cheap to change.

**Why removal order and not strikes.** A player removed at the strike limit has exactly `strikeLimit`
strikes by definition, so ranking the removed by strike total ties all of them and erases the
difference between a player out in round 7 and one who survived to round 20. Removal order is a
longevity proxy and is total ([M5](#m5--removal-from-play)). Since [M4](#m4--the-round-end-reason-determines-removal),
it also has to absorb players removed at *low* strike totals — someone who lapses on their first turn
is removed with one strike, and ranking by strikes would place them above players still competing.
Rule 1 is what prevents that; apply the partition before the sort, never as a tiebreak.

**Rule 5 is deliberate.** A player who quit and a player who was eliminated on merit rank by when they
left, not by how. Ranking withdrawal below elimination would make ghosting cheaper than quitting, which
is the incentive [M4](#m4--the-round-end-reason-determines-removal) exists to close.

`standings` is defined for `MatchInProgress` and `MatchOver` alike; mid-match it is a running view.

**A match that ended by the fewer-than-two-active clause has no ties**: one active player, and the
removed are totally ordered. A match that ended on the strike limit under `EndMatch` may have several
active players sharing a rank.

### M11 — Cross-round exclusions accumulate under hard mode

Under `reuse == Forbidden`, after each round the entities of `result.chain` are unioned into
`excludedActorIds` / `excludedMovieIds` by type, and `nextRound` passes them to the engine.

Under `reuse == Allowed` both sets stay empty and are passed empty. This is the default mode: a new
round makes every entity available again.

**`result.losingMove` is not excluded.** It was never accepted into the chain — `RoundOver` separates
the two fields precisely so this distinction is expressible — so it was never played, and banning it
would punish a guess.

**A voided round contributes nothing.** [`withdraw`](#m16--withdrawal) discards the round in flight
without producing a `RoundOver`, so its entities are never accumulated and are available again in the
replacement round. This follows from exclusions being seeded by `applyRoundResult` alone.

The sets grow monotonically across rounds, so match state under hard mode grows with entities played.
Note also that [ADR 019](DECISIONS.md) measured exhausted-frontier risk as rare under **empty**
exclusion sets; that measurement does not transfer to a mode that thins the frontier every round. It is
unmeasured, not known to be a problem.

### M12 — Every match terminates

Given that rounds keep completing, a match ends within `strikeLimit × |matchOrder|` rounds under either
policy.

Each round charges exactly one strike ([M3](#m3--a-round-loss-costs-exactly-one-strike)). Under
`EndMatch` the match ends once any player reaches `L`, so at most `N(L−1) + 1` rounds are played. Under
`Eliminate` it ends at one active player: `N−1` players at `L` strikes each plus a survivor with at
most `L−1` is at most `LN − 1` strikes, hence at most that many rounds. Removal by lapse or withdrawal
only shortens a match — it retires a player in one round or none.

**Termination is joint, exactly as it is at the round layer**
([ENGINE_CONFORMANCE.md R17](ENGINE_CONFORMANCE.md#r17--every-round-terminates)). The match layer bounds
the match given that rounds complete. It does not bound a match where nobody moves — that is the
session layer's deadline, one level up from the retry loop R17 delegates. What
[M4](#m4--the-round-end-reason-determines-removal) changes is the cost of exercising that bound: one
deadline per absent player rather than `strikeLimit` of them.

Unlike R17's ~95,000-move chain bound, `L × N` is small enough to plan persistence and payload sizes
against.

### M13 — The match layer is pure

`applyRoundResult`, `withdraw`, `nextRound`, and `standings` are pure functions: no I/O, no clock, no
randomness, no graph access, no mutation of arguments. Called twice with equal arguments they return
equal results.

The consequences are the engine's, one layer up. Randomness — a shuffled opening `matchOrder` — is
resolved by the session layer before the match exists, and arrives as data. So is the clock: this layer
never decides that a deadline lapsed, only what a lapse costs.

### M14 — Malformed input is an error, never a match outcome

These are caller defects and must raise, not resolve to a `MatchOutcome`:

- `applyRoundResult` or `withdraw` on a `MatchOver` — no operation applies to a terminal state
- `roundIndex != match.roundsPlayed` ([M15](#m15--a-round-result-applies-once))
- `result.loserIndex` out of range for the round's roster
- `withdraw` naming a player not in `matchOrder`, or one already removed
- `strikeLimit < 1`, `matchOrder` shorter than two entries, or containing duplicates
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

`withdraw` needs no equivalent. It is idempotent by rejection: a second call names an already-removed
player and raises.

**This is detection, not idempotent replay.** The pure layer refuses the stale call; the session layer
maps that refusal onto the stored outcome for the round in question, which is where the
compare-and-swap and any client-supplied move ID already live ([AGENTS.md](../AGENTS.md), *Deployment*).

### M16 — Withdrawal

```
withdraw(match, player) -> MatchOutcome
```

The player is removed with cause `Withdrew`. No strike is charged, no round is recorded, and
`roundsPlayed` does not advance. If the withdrawing player is `nextOpener`, the opener advances first
([M7](#m7--the-next-opener-is-the-next-active-player-in-match-order)). If fewer than two active players
remain, the match ends ([M6](#m6--match-end)).

**Withdrawal and a lapse cost the same thing, and that is the point.** Stopping mid-match is always
available by simply not responding, so any rule that prices an explicit withdrawal differently from
abandonment makes one of the two the smarter way to quit. Pricing withdrawal *above* a lapse rewards
ghosting, which is the behavior that costs every other player time. Pricing it *below* makes quitting
an escape hatch from a losing position. Equality is the only setting with neither property, and
[M4](#m4--the-round-end-reason-determines-removal) is what makes it reachable — before a lapse removed
the player, the two could not be equated without synthesizing strikes.

**The round in flight is voided.** A withdrawal can arrive at any moment, including when it is not the
withdrawing player's turn. The engine's roster is fixed for a round's duration — *"the engine never
adds or removes players mid-round... a match layer that drops an eliminated player does so between
rounds"* ([ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md#data-model)) — so the round cannot continue at
one fewer player. It also cannot be completed, since finishing it needs turns from someone who has
left. The session layer discards the round state without producing a `RoundOver`; no strike is charged
to anyone, and the replacement round is built from `nextRound(match)`.

**A lapse does not void anything, and the asymmetry is forced.** A deadline lapses only on its owner's
turn, so `forfeit` is always legal at that instant and the round ends properly before the removal is
applied. Withdrawal has no such guarantee. The two paths agree on the outcome for the player and differ
only in what happens to the round they were in.

---

## Match boundary

Required by the product, enforced elsewhere. A match layer that enforces these is over-scoped.

| Concern | Enforced by |
|---|---|
| Whether a chain is valid; who lost a round | Round engine |
| Choosing `matchOrder[0]`, or shuffling the order | Session layer, before the match exists ([M13](#m13--the-match-layer-is-pure)) |
| Detecting a lapsed deadline, and calling `forfeit(state, DeadlineLapsed)` | Session layer ([ENGINE_CONFORMANCE.md R7](ENGINE_CONFORMANCE.md#r7--forfeit-ends-the-round)) |
| Discarding the round in flight when a player withdraws | Session layer ([M16](#m16--withdrawal)) |
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

A round result naming seat `i` is written `loss(i)`. Unless a case says otherwise the reason is
`Unconnected` and the chain is irrelevant to the assertion. `lapse(i)` is the same result with
`reason == DeadlineLapsed`.

**Two properties hold across the suite; preserve both when translating.**

*Every GIVEN match state is legally reachable* — reachable by applying some sequence of round results
and withdrawals from a fresh match under the stated config. A case asserting behavior from an
unreachable state proves nothing.

*Each case isolates one rule.* Where a state could trigger more than one transition, the fixtures are
chosen so exactly one applies. [MC-05](#mc-05--the-two-limit-policies-coincide-in-a-two-player-match)
and [MC-10](#mc-10--a-seat-index-does-not-survive-a-roster-change) are the exceptions; stacking is what
they exist to pin.

### The outcome table

One strike is charged in every row ([M3](#m3--a-round-loss-costs-exactly-one-strike)).

| # | Policy | `reason` | Loser's strikes before | Active before | Outcome |
|---|---|---|---|---|---|
| MC-01 | either | `Unconnected` | 0 | 4 | `MatchInProgress`; strikes 1; no removal |
| MC-02 | `EndMatch` | `Unconnected` | 2 (limit 3) | 4 | `MatchOver`; loser has 3; `removed` empty |
| MC-03 | `Eliminate` | `Unconnected` | 2 (limit 3) | 4 | `MatchInProgress`; removed, cause `StrikeLimit`; 3 active |
| MC-04 | `Eliminate` | `Unconnected` | 2 (limit 3) | 2 | `MatchOver`; loser removed; one active remains |
| MC-20 | either | `GaveUp` | 0 | 4 | Identical to MC-01 |
| MC-23 | either | `DeadlineLapsed` | 0 | 4 | `MatchInProgress`; strikes 1; **removed**, cause `Lapsed`; 3 active |

### Group A — Strikes, removal, and match end

#### MC-01 — A round loss charges one strike to the round's loser

GIVEN a fresh match, `ELIM_3`, all strikes 0, `nextOpener = P0`, `roundsPlayed = 0`
WHEN `applyRoundResult(match, 0, loss(2))`
THEN `MatchInProgress`; `strikes = {P0:0, P1:0, P2:1, P3:0}`; `removed` empty; `roundsPlayed = 1`

Seat 2 of roster `[P0, P1, P2, P3]` is P2. No other player's total changes.

#### MC-02 — Reaching the limit under EndMatch ends the match

GIVEN `END_3`, `strikes = {P0:0, P1:2, P2:1, P3:0}`, `nextOpener = P0`
WHEN a result naming P1 is applied with reason `Unconnected`
THEN `MatchOver`; `strikes[P1] == 3`; `removed` is empty

`EndMatch` never removes on the strike limit ([M5](#m5--removal-from-play)) — assert the empty list,
not just the outcome.

#### MC-03 — Reaching the limit under Eliminate removes the player and continues

GIVEN `ELIM_3`, `strikes = {P0:0, P1:2, P2:1, P3:0}`, `nextOpener = P0`
WHEN a result naming P1 is applied with reason `Unconnected`
THEN `MatchInProgress`; `removed == [(P1, StrikeLimit)]`; active is `{P0, P2, P3}`;
`nextRound().playerCount == 3`

#### MC-04 — The last removal ends the match

GIVEN `ELIM_3`, `removed == [(P1, StrikeLimit), (P3, Lapsed)]`, `strikes = {P0:1, P1:3, P2:2, P3:1}`,
`nextOpener = P0`
WHEN a result naming P2 is applied with reason `Unconnected`
THEN `MatchOver`; P2 appended with cause `StrikeLimit`; P0 is the only active player

The match ends because fewer than two active players remain ([M6](#m6--match-end)) — not because a
count of removals was reached. Note P3 was removed at one strike, which is reachable only through
[M4](#m4--the-round-end-reason-determines-removal).

#### MC-05 — The two limit policies coincide in a two-player match

GIVEN two matches over `matchOrder = [P0, P1]`, identical but for `onLimit`, `strikes = {P0:0, P1:2}`,
limit 3
WHEN a result naming P1 with reason `Unconnected` is applied to each
THEN both return `MatchOver` with `strikes[P1] == 3`, and `standings` ranks P0 first in both

The two differ only in `removed`: one entry under `Eliminate`, empty under `EndMatch`. Rank is
unaffected, which is the point — [M10](#m10--standings) rule 1 is vacuous when one player is active and
one is removed.

#### MC-20 — Giving up costs a strike and nothing more

GIVEN a fresh `ELIM_3` match
WHEN `loss(2)` and the same result with reason `GaveUp` are each applied to it
THEN both return equal `MatchInProgress` values

Pins the top two rows of [M4](#m4--the-round-end-reason-determines-removal): a give-up is a move, and
is priced as one.

#### MC-23 — A lapsed deadline removes the player

GIVEN a fresh `ELIM_3` match, all strikes 0, `nextOpener = P0`
WHEN `applyRoundResult(match, 0, lapse(2))`
THEN `MatchInProgress`; `strikes[P2] == 1`; `removed == [(P2, Lapsed)]`; `nextRound().playerCount == 3`

Both halves matter. The strike is charged because a round was lost
([M3](#m3--a-round-loss-costs-exactly-one-strike)), which is what keeps
`sum(strikes) == roundsPlayed` true. The removal is independent of the strike total — P2 is at one
strike against a limit of three.

#### MC-24 — A lapse removes under EndMatch too, without ending the match

GIVEN `END_3`, all strikes 0, four active players
WHEN `lapse(1)` is applied
THEN `MatchInProgress`; `removed == [(P1, Lapsed)]`; three active players remain

`EndMatch` suppresses removal on the strike limit only ([M5](#m5--removal-from-play)). An
implementation that reads `EndMatch` as "nobody is ever removed" fails here.

#### MC-25 — Lapses can end an EndMatch match without anyone reaching the limit

GIVEN `END_3`, `strikes = {P0:1, P1:1, P2:1, P3:1}`, `removed == [(P1, Lapsed), (P3, Lapsed)]`, two
active players, `roundsPlayed == 4`
WHEN `lapse(·)` naming P2 is applied
THEN `MatchOver`; P0 is the only active player; no player has reached `strikeLimit`

The universal clause in [M6](#m6--match-end). Without it this state is stuck: the match cannot end,
and the engine cannot start a round at one player.

### Group B — Rotation and rosters

#### MC-06 — The opener rotates by one active position per round

GIVEN `ELIM_3`, no removals, `nextOpener = P0`
WHEN four results are applied in sequence
THEN `nextOpener` is P1, P2, P3, P0 after each

Rotation is independent of who lost: assert this with the same seat losing every round.

#### MC-07 — Rotation skips a removed player

GIVEN `ELIM_3`, `removed == [(P2, Lapsed)]`, `nextOpener = P1`
WHEN a result is applied that removes nobody
THEN `nextOpener == P3`

P2 holds their position in `matchOrder` and is skipped, not deleted
([M2](#m2--the-match-order-is-fixed)).

#### MC-08 — Rotation is well-defined when the opener is removed by the operation just applied

GIVEN `ELIM_3`, all strikes 0, `nextOpener = P1`, no prior removals
WHEN `lapse(0)` is applied — seat 0 is P1, the opener
THEN `MatchInProgress`; `removed == [(P1, Lapsed)]`; `nextOpener == P2`

The scan starts strictly after P1's position in `matchOrder`, which P1 still occupies. An
implementation that deletes the player before advancing has no position to scan from.

This is why [M7](#m7--the-next-opener-is-the-next-active-player-in-match-order) fixes the order of
evaluation. Run the mirror against `withdraw(match, P1)` from the same state: same expectation, and it
is the asynchronous path where the coupling is easiest to break.

#### MC-09 — The roster is match order, filtered and rotated

GIVEN `ELIM_3`, `removed == [(P1, StrikeLimit)]`, `nextOpener = P2`
THEN `nextRound().roster == [P2, P3, P0]` and `playerCount == 3`

Opener at index 0; the rest follow `matchOrder` cyclically.

#### MC-10 — A seat index does not survive a roster change

GIVEN `ELIM_3`, `removed == [(P1, StrikeLimit)]`, `nextOpener = P2`, so `roster == [P2, P3, P0]`
WHEN `loss(1)` is applied
THEN `strikes[P3]` increases, and `strikes[P1]` does not

Seat 1 is P3 in this round and was P1 in the opening round. A match layer resolving `loserIndex`
against `matchOrder` charges P1 — a player who is not even in the round
([M9](#m9--a-seat-index-is-round-local)). This is the highest-value case in the suite; an
implementation that passes everything else and fails this one silently corrupts every match that
reaches a removal.

### Group C — Standings

#### MC-11 — Active players outrank removed players regardless of strikes

GIVEN `ELIM_3`, `strikes = {P0:2, P1:1, P2:0, P3:1}`, `removed == [(P1, Lapsed)]`
THEN `standings` ranks P2 first, then P3, then P0, then P1 — strike totals 0, 1, 2, 1 respectively

P1 has fewer strikes than P0 and still ranks below, because the partition is applied before the sort
and never as a tiebreak ([M10](#m10--standings) rule 1). This ordering is reachable only since
[M4](#m4--the-round-end-reason-determines-removal); before it, every removed player sat at the limit
and the partition and the sort agreed by accident.

#### MC-12 — Equal strike totals share a rank

GIVEN `END_3`, `strikes = {P0:1, P1:1, P2:0, P3:2}`, no removals
THEN ranks are P2 = 1, P0 = 2, P1 = 2, P3 = 4

Standard competition ranking: the tie group of two consumes ranks 2 and 3, and the next distinct rank
is 4. **[draft default]** — a dense-ranking implementation (1, 2, 2, 3) fails this case and is a
one-line change if preferred.

#### MC-13 — Removed players rank in reverse removal order, whatever the cause

GIVEN `ELIM_3` at `MatchOver`, `removed == [(P1, Lapsed), (P3, Withdrew), (P2, StrikeLimit)]`,
`strikes = {P0:1, P1:1, P2:3, P3:0}`
THEN ranks are P0 = 1, P2 = 2, P3 = 3, P1 = 4, with no shared ranks

Three different causes and three different strike totals, none of which affects the order
([M10](#m10--standings) rules 4 and 5). P3 withdrew at zero strikes and still outranks P1, who lapsed
earlier — later departure ranks higher.

#### MC-14 — A match ended by the fewer-than-two-active clause has no ties

GIVEN any `MatchOver` reached with exactly one active player
THEN every rank in `standings` is distinct

A structural property, not a fixture: one active player, and removals are totally ordered
([M5](#m5--removal-from-play)). It does **not** hold for a match ended by the strike limit under
`EndMatch`, where several active players can share a rank — assert that variant separately rather than
generalizing this one.

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

### Group E — Withdrawal

#### MC-26 — Withdrawal removes the player and charges no strike

GIVEN `ELIM_3`, `strikes = {P0:1, P1:2, P2:1, P3:1}`, `nextOpener = P0`, `roundsPlayed = 5`
WHEN `withdraw(match, P1)`
THEN `MatchInProgress`; `removed == [(P1, Withdrew)]`; `strikes[P1] == 2` unchanged;
`roundsPlayed == 5` unchanged; three active players

No strike, no round. P1 sat one strike from the limit and their total is untouched — withdrawal is a
removal, not a penalty ([M16](#m16--withdrawal)).

#### MC-27 — Withdrawal can end the match

GIVEN `ELIM_3`, `strikes = {P0:0, P1:1, P2:3, P3:0}`, `removed == [(P1, Lapsed), (P2, StrikeLimit)]`,
two active players
WHEN `withdraw(match, P3)`
THEN `MatchOver`; P0 is the only active player

[M6](#m6--match-end)'s universal clause, reached through `withdraw` rather than `applyRoundResult`.

#### MC-28 — Withdrawing twice raises

GIVEN any `MatchInProgress` where `withdraw(match, P1)` has been applied
WHEN `withdraw` names P1 again on the result
THEN it raises ([M14](#m14--malformed-input-is-an-error-never-a-match-outcome))

Also assert that `withdraw` naming a `PlayerId` absent from `matchOrder` raises.

### Group F — Purity and input validation

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
WHEN `applyRoundResult` or `withdraw` is called
THEN it raises ([M14](#m14--malformed-input-is-an-error-never-a-match-outcome))

`standings` remains callable on `MatchOver` — that is its final form.

#### MC-21 — An out-of-range seat index is an error

GIVEN `ELIM_3`, `removed == [(P1, StrikeLimit)]`, so `playerCount == 3`
WHEN a result with `loserIndex == 3` is applied
THEN it raises

Valid against the four-player opening roster, invalid here. A match layer that resolves against
`matchOrder` accepts it and charges the wrong player, which is
[MC-10](#mc-10--a-seat-index-does-not-survive-a-roster-change) in its silent form.

#### MC-22 — Match construction is validated

Each of these raises at construction: `strikeLimit == 0`; `matchOrder` with one entry; `matchOrder`
containing a duplicate `PlayerId`; `nextOpener` not present in `matchOrder`.

---

## Open questions

**Whether a single lapse is too harsh.** [M4](#m4--the-round-end-reason-determines-removal) removes a
player on their first missed deadline and cannot distinguish someone who has left from someone briefly
unreachable. The revisit trigger is playtest evidence that engaged players are being removed by
travel or inattention rather than by quitting — not a threshold set in advance. The mitigation shape is
known and additive: correspondence chess grants per-player time banks, which is session-layer state and
needs no structural room reserved here. **Do not pre-emptively soften the rule instead**; a lapse that
costs less than a withdrawal reopens the incentive gap [M16](#m16--withdrawal) exists to close.

**Whether hard mode needs a frontier guard.**
[M11](#m11--cross-round-exclusions-accumulate-under-hard-mode) accumulates exclusions monotonically,
thinning the graph frontier every round. [ADR 019](DECISIONS.md) measured exhausted-frontier risk as
rare under empty exclusion sets; that result does not transfer. Unmeasured, and not blocking — hard mode
is not the default.

**Whether `EndMatch` should end the match at all when a leader is absent.** Under `EndMatch`, reaching
the strike limit ends the match for everyone. A player who is losing can therefore truncate the series
by losing `strikeLimit` rounds on purpose. They cannot improve their own standing by doing it — they
finish last — so the exposure is griefing rather than a competitive exploit, and it is narrow now that
lapses remove rather than accumulate. Left as written; revisit if a playtest produces it.

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
| [ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md) | The layer below. Produces the `RoundOver` this document consumes; its [Engine boundary](ENGINE_CONFORMANCE.md#engine-boundary) table delegates to this document. [M4](#m4--the-round-end-reason-determines-removal) is what gives `RoundOver.reason` its differential — the use the engine spec asserted and did not specify |
| [DECISIONS.md](DECISIONS.md) | [ADR 021](DECISIONS.md) established the round outcome taxonomy this layer reads; [ADR 012](DECISIONS.md)/[018](DECISIONS.md) the deadline model the session layer owns |
| [AGENTS.md](../AGENTS.md) | Operating rules. Its match-layer summaries are superseded by this document and need reconciling once it is accepted |
| [PLANNING_AGENDA.md](PLANNING_AGENDA.md) | §4.1 is this document's commissioning entry |
