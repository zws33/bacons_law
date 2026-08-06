# 001 — Actor degree distribution and round-ending moves

> **AUTHORITY: investigation record, not a specification. Nothing here is binding.**
> Rules live in [`../../AGENTS.md`](../../AGENTS.md). Decisions live in
> [`../DECISIONS.md`](../DECISIONS.md). See [the directory charter](README.md).
>
> **STATUS: `IN PROGRESS`** — pre-registered 2026-08-06. **No measurements have been taken.**
> Every hypothesis below is marked `UNRESOLVED`, and the Results and Findings sections are
> deliberately empty. Do not cite anything in this document as a fact about the graph.

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

**H1 · UNRESOLVED** — *Most degree-1 actors are genuine, not cap-induced.* Specifically, **≥60%**
of degree-1 actors appear in exactly one graph-eligible film in the raw data.
*Confidence: low.* Genuinely uncertain and it could go either way. The raw data is already
restricted to films with ≥5 sitelinks and an English Wikipedia article, which filters toward
notable films whose cast lists tend to be well populated — but `cast_cap` ranks by the actor's own
sitelinks, so a low-notability person can be cut from a large cast while surviving in a small one.

**H2 · UNRESOLVED** — *Degree-1 actors concentrate in films whose raw cast list never hit the cap.*
The rate of degree-1 cast members is higher among films with ≤15 raw cast entries than among films
with >15. *Confidence: high.* This follows mechanically from `_cap_cast`: capping only bites above
15, and when it bites it keeps the most notable, who tend to have other credits. Below 15 nothing
is filtered, so a zero-sitelink one-credit person survives — `min_sitelinks` gates **films, not
actors**.

**H3 · UNRESOLVED** — *Film notability correlates positively with raw cast-list length.* Popular
films get better-curated Wikidata entries. *Confidence: medium-high.* If true, H2's concerning
population sits mostly in obscure films, and cheap kills are rare by construction.

**H4 · UNRESOLVED** — *Cheap kills are rare.* Among the top decile of films by sitelinks, **fewer
than 15%** have at least one degree-1 actor in their graph cast. *Confidence: medium.* This is the
number that actually decides whether anything needs fixing. H2 and H3 both support it, but it is
the load-bearing prediction and worth the least confidence for exactly that reason.

**H5 · UNRESOLVED** — *The [issue #19](https://github.com/zws33/bacons_law/issues/19) confound is
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

> **EMPTY — nothing has been measured.** This section is filled in after execution.

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
