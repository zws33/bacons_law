# 001 — Actor degree distribution and round-ending moves

> **AUTHORITY: investigation record, not a specification. Nothing here is binding.**
> Rules live in [`../../AGENTS.md`](../../AGENTS.md). Decisions live in
> [`../DECISIONS.md`](../DECISIONS.md). See [the directory charter](README.md).
>
> **STATUS: `IN PROGRESS`** — pre-registered 2026-08-06 (commit `8048a96`), measured 2026-08-06
> (commit `efff2a0`). Results are recorded below; **Findings and promoted conclusions are not yet
> written.** Four hypotheses confirmed, one falsified.
>
> Raw output: [`001-data/summary.json`](001-data/summary.json). Reproduce with
> `cd etl && uv run python -m analysis.degree_distribution`.

**Question.** How often does the graph let a player end a round cheaply — and is it common enough
to change the data, the rules, or neither?

**Artifact under study.** `etl/data/graph/v1` — 47,624 movies, 89,074 actors, 456,129 edges, built
1925–2026 with `cast_cap=15`, `min_cast=3`, `min_sitelinks=5`.

---

## Why this investigation exists

The ETL is the settled part of this project, and it has produced a full-range artifact that
nothing consumes yet. Before building a server against it, it is worth knowing whether the graph
makes a good game — and one property in particular has a consequence that reaches past the ETL
into the engine's contract.

A player whose every graph neighbour is already in the chain has **no legal move**. The round ends
and they are named the loser, identically to a player who simply guessed wrong. The round engine
cannot currently express the difference, and
[`../ENGINE_CONFORMANCE.md`](../ENGINE_CONFORMANCE.md) records this as an open question. Whether
that question needs answering at all depends on how often the situation arises, which is a
measurement nobody has taken.

Doing this before the planning session is deliberate: the answer could change the ETL dials, and
dial changes that require a re-extract are the expensive kind. Anything learned here batches with
[issue #19](https://github.com/zws33/bacons_law/issues/19)'s deferred query fixes into a single
rebuild.

---

## What we are actually asking

**Not** "how many degree-1 actors are there." That framing was wrong, and correcting it is
recorded in [Revisions to our own framing](#revisions-to-our-own-framing) below.

Naming an actor whose only credit is the film in play is a **legitimate winning move.** Knowing
that an actor has exactly one credit is precisely the knowledge this game tests, and steering
play into obscure territory is strategy. Obscurity is the skill gradient — the design should not
try to flatten it, and a player who studies deep cuts *should* win more.

The real question is whether the knowledge required to end a round is **proportionate to the
reward**:

|  | Description | Verdict |
|---|---|---|
| **Earned kill** | Reaching the dead end required first steering into a little-known film. You knew the obscure film; you earned the round. | The game working as intended. |
| **Cheap kill** | Anyone names a household-name film, and one bit-part credit from it ends things. | Compresses rounds — the kill is available from positions everyone reaches. |

A second distinction determines whether this is a data problem at all:

|  | Description | Verdict |
|---|---|---|
| **Genuine** | The actor really does appear in exactly one film in the source data. | Legitimate content. Keep. |
| **Cap-induced** | The actor has a filmography, but `cast_cap=15` truncated them out of every film but one. | A build artifact. |

Cap-induced degree-1 is the same defect as the false-rejection problem seen from the other side:
that actor's other films are ones a knowledgeable player might name and be *rejected* for.

**These two splits are the investigation.** The raw count of degree-1 actors answers neither.

---

## Priors and hypotheses

Pre-registered before any measurement. **The wording below is never edited to match the outcome** —
only the status token changes. A prediction that was wrong is the most useful line in this document.

**H1 · CONFIRMED** — *Most degree-1 actors are genuine, not cap-induced.* Specifically, **≥60%**
of degree-1 actors appear in exactly one graph-eligible film in the raw data.
*Confidence: low.* Genuinely uncertain and it could go either way. The raw data is already
restricted to films with ≥5 sitelinks and an English Wikipedia article, which filters toward
notable films whose cast lists tend to be well populated — but `cast_cap` ranks by the actor's own
sitelinks, so a low-notability person can be cut from a large cast while surviving in a small one.

**H2 · CONFIRMED** — *Degree-1 actors concentrate in films whose raw cast list never hit the cap.*
The rate of degree-1 cast members is higher among films with ≤15 raw cast entries than among films
with >15. *Confidence: high.* This follows mechanically from `_cap_cast`: capping only bites above
15, and when it bites it keeps the most notable, who tend to have other credits. Below 15 nothing
is filtered, so a zero-sitelink one-credit person survives — `min_sitelinks` gates **films, not
actors**.

**H3 · CONFIRMED** — *Film notability correlates positively with raw cast-list length.* Popular
films get better-curated Wikidata entries. *Confidence: medium-high.* If true, H2's concerning
population sits mostly in obscure films, and cheap kills are rare by construction.

**H4 · FALSIFIED** — *Cheap kills are rare.* Among the top decile of films by sitelinks, **fewer
than 15%** have at least one degree-1 actor in their graph cast. *Confidence: medium.* This is the
number that actually decides whether anything needs fixing. H2 and H3 both support it, but it is
the load-bearing prediction and worth the least confidence for exactly that reason.

**H5 · CONFIRMED** — *The [issue #19](https://github.com/zws33/bacons_law/issues/19) confound is
small.* Non-human entities wrongly admitted as cast (films, characters, animals — the query places
no `P31 = Q5` constraint on `?actor`) account for **under 10%** of degree-1 actors.
*Confidence: medium.* Nine film-as-actor QIDs are confirmed, but that is a floor, and characters
and animals are unmeasured.

---

## Method

Everything is offline. `graph.json` supplies both adjacency maps; the 102 cached raw partitions in
`etl/data/raw/` supply `actor_sitelinks`, `film_sitelinks`, and pre-cap cast lists. **No re-query
is required.**

Two implementation notes that will otherwise cause wrong answers:

- **Classify nodes by which adjacency map they key**, not by `entities[qid].type`. The `entities`
  map is built last-write-wins on a flat QID-keyed dict, so the QIDs that are both film and cast
  member get an arbitrary type ([issue #19](https://github.com/zws33/bacons_law/issues/19)).
- **Count distinct film QIDs, never raw rows.** `P577` is multi-valued, so a film with a festival
  premiere and a wide release appears in two year partitions; `transform` dedupes on first-seen,
  and analysis must too.

| ID | Measurement | Answers |
|---|---|---|
| **M1** | Degree distribution of `actors_to_movies`. | Shape and the raw degree-1 population. Bounds everything downstream. Movie degree needs no measuring — `min_cast` and `cast_cap` pin it to [3,15] by construction. |
| **M2** | For each degree-1 actor, count distinct graph-eligible films they appear in pre-cap. Split **genuine** (exactly 1) from **cap-induced** (>1). | **H1.** The split that decides whether any remedy is warranted. |
| **M3** | Per film: number of cast members with degree 1, joined to `film_sitelinks`. Report by sitelink decile. | **H4** — the headline number — and the cheap/earned distribution. |
| **M4** | Per film: raw pre-cap cast count vs. `film_sitelinks`, and degree-1 rate split at the cap boundary. | **H2** and **H3**. |
| **M5** | Count QIDs that key both adjacency maps. | **H5**, partially. The film-as-cast share is measurable offline; characters and animals are **not** — that residue needs a Wikidata query and is out of scope here. |

**Conditional.** If M3 shows a meaningful cheap quadrant, simulate notability-weighted walks under
the real rules and report cause of death (exhausted frontier vs. length reached). Skipped
otherwise.

### Decision rule

Committed in advance, and honestly calibrated — these are judgment calls, not derived constants.
They are recorded now so the analysis cannot be rationalized after the fact.

| M3 result (top-decile films offering a one-move kill) | Action |
|---|---|
| **< 15%** | Leave it alone. That is a skill filter, not a defect. Record and move on. |
| **15–40%** | Fix the cap-induced share only; leave genuine one-credit actors untouched. |
| **> 40%** | Rounds compress from common positions. Warrants a dial change and a rebuild. |

**A limit worth stating up front:** the graph can only tell us a kill is *available*, never whether
a player finds it. Those are different numbers, and only playtesting gives the second. This
investigation bounds the problem; it does not settle it.

### Candidate remedies to cost out

Measured while we are in the data, so the decision has prices attached:

- **Cap rescue** — when an actor would otherwise end up degree-1, restore their next-best edge past
  the cap. Targets cap-induced dead ends, leaves genuine ones alone. A `transform`/`emit` change
  testable against the existing interim file, **no re-extract**.
- **Actor sitelink floor** — effective but blunt: it removes genuine obscure actors too, which is
  the content we want to keep. Requires a re-extract, so it batches with issue #19.
- **Raise `min_cast`** — free from the cache, but shrinks the movie set.
- **Policy, not data** — the session layer detects an exhausted frontier and ends the round without
  a strike. Note this is in tension with the framing above: if a dead-end move is a legitimate
  kill, the loser arguably *should* take the strike. A product call this investigation informs but
  does not make.

---

## Results

Measured against `graph/v1` and all 102 raw partitions (1,211,637 rows). Runtime ~2s — I had
predicted "a few minutes"; pydantic v2's Rust core validates far faster than estimated.
`invariant_violations` is empty: movie degree sits in `[3, 15]` exactly as `min_cast` and
`cast_cap` require.

### M1 — degree distribution

| | |
|---|---|
| Actors | 89,074 |
| **Degree-1 actors** | **40,906 (45.9%)** |
| Median actor degree | 2 |
| p90 actor degree | 13 |
| Max actor degree | 188 |
| Movie degree range | [3, 15] ✓ |

Nearly half of all actor nodes are leaves.

### M2 — genuine vs. cap-induced → **H1 CONFIRMED**

| | | |
|---|---|---|
| Genuine (1 raw film) | 34,341 | **83.95%** |
| Cap-induced (>1 raw film) | 6,565 | 16.05% |
| Anomalous (0 raw films) | 0 | — |

Threshold was ≥60% genuine. Of the cap-induced, 4,345 appear in exactly 2 raw films; the tail
reaches 29.

### M3 — kill availability by film notability → **H4 FALSIFIED**

| Decile | Films | Sitelinks | % with ≥1 kill | Mean kills | Mean cast | Kills ÷ cast |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 4,762 | 5–5 | 41.4% | 0.85 | 8.85 | 9.6% |
| 1 | 4,762 | 5–6 | 46.3% | 1.02 | 8.47 | 12.1% |
| 2 | 4,763 | 6–7 | 41.7% | 0.88 | 8.22 | 10.8% |
| 3 | 4,762 | 7–8 | 41.0% | 0.84 | 8.68 | 9.6% |
| 4 | 4,763 | 8–9 | 40.4% | 0.82 | 9.06 | 9.1% |
| 5 | 4,762 | 9–11 | 42.0% | 0.85 | 8.95 | 9.5% |
| 6 | 4,762 | 11–13 | 41.9% | 0.84 | 9.35 | 8.9% |
| 7 | 4,763 | 13–18 | 41.7% | 0.84 | 10.27 | 8.2% |
| 8 | 4,762 | 18–27 | 43.9% | 0.87 | 11.11 | 7.8% |
| **9** | 4,763 | **27–138** | **42.8%** | 0.79 | 12.83 | **6.1%** |

Predicted <15% in decile 9; measured **42.8%**. Falsified by a wide margin.

**The pre-registered metric saturates.** "% with ≥1 kill" is flat across every decile — not
because no gradient exists, but because the measure cannot detect one: with 9–13 cast members and
a 6–12% per-actor rate, P(at least one) is high everywhere. The rightmost column, computed
post-hoc, shows the gradient the hypothesis was reaching for — 9.6% → 6.1%, a 36% relative
decline. **That does not rescue H4**, which was stated on the saturating metric and stands
falsified.

**A second design flaw:** the decile boundaries are compressed. Deciles 0–4 span sitelinks 5–9,
and decile 9 begins at 27. "Top decile" therefore means 4,763 films with ≥27 sitelinks, which is
much broader than "films players will actually name" — genuinely famous films sit at 100+. The
question H4 meant to ask is still unanswered at the right end of the distribution.

### M4 — cast length and the cap boundary → **H2 and H3 CONFIRMED**

| Decile | Mean raw cast | % capped |
|---:|---:|---:|
| 0 | 10.10 | 17.2% |
| 9 | 18.73 | 52.4% |

Cast-list length rises monotonically with film notability (**H3**), from 10.1 to 18.7, and the
share of films the cap actually bites rises from 17% to 52%.

| | Films | Mean degree-1 rate |
|---|---:|---:|
| Capped (raw cast > 15) | 10,642 | **6.2%** |
| Uncapped (raw cast ≤ 15) | 36,982 | **11.2%** |

Uncapped films carry nearly double the degree-1 rate (**H2**), exactly as the mechanism predicts:
capping keeps the most notable, who have other credits, while below the cap nothing filters actors
at all.

### M5 — non-human cast → **H5 CONFIRMED**

Nine QIDs key both adjacency maps — **0.02%** of degree-1 actors, against a <10% threshold. They
are precisely the nine films [issue #19](https://github.com/zws33/bacons_law/issues/19) identified
(Troll 2, Bob Roberts, Jaws 2, Friday the 13th, Yamakasi, Jimmy Hollywood, Zarak, Sujata, Max
Rose), reproduced independently here. Characters, animals, and groups remain **unmeasured** — they
need a Wikidata query, so this is a floor.

### M6 — actor notability (post-hoc, resolves no hypothesis)

Added after the first run exposed a gap: M3 counts a kill whether or not any player has heard of
the actor. Thresholds were chosen after seeing the data, so nothing here confirms or falsifies
anything.

| Group | n | Median | p75 | p90 | p99 |
|---|---:|---:|---:|---:|---:|
| Degree-1 actors | 40,906 | **4** | 9 | 17 | 60 |
| Multi-credit actors | 48,168 | **11** | 19 | 34 | 91 |

Degree-1 actors are systematically far less notable — median 4 sitelinks against 11.

| Actor sitelink floor | Degree-1 actors above it | % of all films with a nameable kill | % of top-decile films |
|---:|---:|---:|---:|
| 0 (M3's measure) | 40,906 | 42.3% | 42.8% |
| ≥10 | 9,491 | **15.2%** | **23.3%** |
| ≥25 | 2,302 | 3.8% | 8.1% |
| ≥50 | 632 | 1.0% | 2.4% |

Requiring only that the killing actor have ten language Wikipedias cuts availability from 42% to
15%. At ≥25 it is 3.8%.

**The gradient inverts under the floor.** Unfiltered, kill availability is flat across deciles.
Filtered to nameable actors, notable films carry *more* (23.3% vs. 15.2% overall) — because
notable films have more notable cast throughout, including their one-credit members. Cheap kills
concentrate in exactly the films players name most, but at low absolute rates.

---

## Findings

> **EMPTY — no findings exist.** Do not cite this document as evidence of anything about the graph
> until this section is populated and the status at the top reads `COMPLETE`.

---

## What changed as a result

> **EMPTY.** On completion, anything binding is promoted out — to an ADR, to `AGENTS.md`, to
> `ENGINE_CONFORMANCE.md`'s exhausted-frontier open question, or to the ETL dials — and linked from
> here. This document records evidence and reasoning; it is never where a rule lives.

---

## Revisions to our own framing

Kept because the correction is more instructive than the measurement will be.

**"Trap" was the wrong word, and it smuggled in a conclusion.** The investigation was first scoped
around a "trap rate" — the share of edges leading to a dead end — and described a player steering
the chain into one as *exploiting* the graph. Both framings treat a degree-1 move as something to
eliminate.

That is backwards for this game. The skill axis **is** knowledge of actor/film relationships, so
knowing an actor has exactly one credit is the game working, not a hole in it. Calling it an
exploit is like calling a forced mate an exploit. It also pointed at the wrong remedy: the first
plan proposed an iterative k-core prune removing every degree-1 actor, which would have deleted
precisely the obscure content that gives the game its skill gradient — and there is a real
incentive for players to study obscure films and actors in order to compete.

The corrected framing produced two better questions (cheap vs. earned, genuine vs. cap-induced),
one of which — the cap-induced split — the original plan could not have asked at all, because it
had already decided that all degree-1 actors were the same thing.

**The transferable version:** when a metric implies a remedy before it has been measured, the
framing is probably carrying a value judgment. "Trap rate" presumes traps are bad. "Cheap versus
earned" does not presume anything, and it is measurable.
