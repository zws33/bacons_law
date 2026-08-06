# Planning session agenda

> **This is an INPUT to the planning session, not a roadmap and not a status document.**
> It exists to stop the session rediscovering what is already settled. It records no decisions of
> its own — every "open" item below is open precisely because nobody has decided it.
>
> **Delete this file once the session has produced its ADRs.** A consumed agenda that survives as
> a document is how a project ends up with two sources of truth. Nothing should ever link to it.
>
> Prepared 2026-08-06, after [ADR 018](DECISIONS.md) and [ADR 019](DECISIONS.md).

---

## 1. Settled — do not re-litigate

These follow from the ETL contract and hold across any rewrite in any language. Discarding one
discards the reason `etl/` exists. Full statements in [`../AGENTS.md`](../AGENTS.md) under
Architecture Boundaries → Binding.

- Validation data is **precomputed offline** into a versioned artifact, loaded read-only at boot.
  No per-turn external API call, ever.
- **Validation is co-located with the graph, in-process.** The engine/data seam must never cross a
  network hop.
- **Cast IDs are Wikidata QID strings.** ID adaptation is loader-side; never pre-map to integers.
- **Movies only, CC0 Wikidata, no API key.**
- **The engine is pure** — no I/O, no platform dependencies.
- **The round engine names a loser, never a winner**; strikes and elimination are the match layer's.
- **Multiplayer N > 2 ships day one.**

`etl/` is the one fixed contract and is not on the agenda.

---

## 2. Recently un-constrained — this is the part that changed

**Read this before evaluating anything.** The previous planning input was biased by an assumption
that has since been withdrawn, and the criteria it implied are gone with it.

[ADR 018](DECISIONS.md) established that the game is turn-based and *real-time is a time control,
not an architecture*. Consequences that widen the decision space:

| Was constrained | Now |
|---|---|
| Stack selected by concurrency model — green threads, idle-socket memory, broadcast fan-out | **Free.** Evaluate on ordinary request/response criteria. A boring stack is fully admissible. |
| Single long-lived instance required | **No such constraint.** The graph is read-only and identical everywhere; N instances coordinate nothing. |
| Scale-to-zero ruled out | **Viable.** Cold start measured at ~175 ms for the 21.4 MB artifact (CPython, the slowest realistic option). |
| Durable store paired with a presence/broadcast layer | **Store only.** There is no presence layer to choose. |
| Horizontal scaling deferred as a pair (locking + broadcast) | **Neither paired nor blocked.** CAS on the store covers it. |

⚠️ **[`investigations/000-system-design-case-study.md`](investigations/000-system-design-case-study.md)
§5 and §6 are superseded and must not be used to pick a stack.** §6 scores runtimes on idle-socket
memory and broadcast fan-out — a workload this system does not have. It carries markers, but it is
the single most likely source of a wrong turn in this session.

---

## 3. Decisions to make

### 3.1 Server language and framework

**Criteria, post-018:** ecosystem and library maturity; how cleanly the language expresses the
round engine's sealed-union state machine (`Move = Actor | Movie`, exhaustive matching); deployment
simplicity; familiarity; and whether types can be shared with the client.

**What makes this reversible:** [`ENGINE_CONFORMANCE.md`](ENGINE_CONFORMANCE.md) is language- and
framework-agnostic and generates a conformance suite in any stack. The rules do not live in the
implementation, so choosing a language is no longer also choosing where the rules live.

**In the tree:** Kotlin/Ktor `:backend` (still a TMDB proxy) and a pure Kotlin `:core`. Both are
prototypes with no claim on the outcome.

### 3.2 Durable store

**Requirements** (from [ADR 012](DECISIONS.md), unaffected by 018): serializable state; survives
restarts; spans days for correspondence; compare-and-swap on a version; **never behind a TTL.**

**Now simpler:** no cache or pub/sub layer to pair with it.

**Worth weighing:** with polling as the notification mechanism, reads substantially outnumber
writes. The store's read path matters more than its write path.

### 3.3 Hosting

Fully open. Cold start is not an obstacle (§2). Decide on cost, operational simplicity, and
familiarity.

### 3.4 Client

**In the tree:** an unmaintained Android/Compose app built for the dropped pass-the-phone design.
Web is untried.

**Constraint worth surfacing early:** [ADR 013](DECISIONS.md)'s identity is device-anchored and
carries push tokens, and push is the correspondence notification path. Push is straightforward on
mobile and clunkier on web. This couples the client decision to the notification design more
tightly than it looks.

---

## 4. Specs that do not exist

### 4.1 The match layer — nothing is written

[`ENGINE_CONFORMANCE.md`](ENGINE_CONFORMANCE.md) defines the seam it must attach to and stops
there. Needs specifying: strike accounting; whether a strike limit eliminates a player or ends the
match; standings across a series; mode configuration; who opens the next round; and whether
entities used in earlier rounds stay available (the engine already accepts
`excludedActorIds`/`excludedMovieIds` for this).

### 4.2 The typeahead — the least-designed, highest-traffic part of the system

Nothing has been designed for it, and it is **the highest-frequency operation by a wide margin** —
far above move submission. 89,074 actors and 47,624 movies to resolve names against, with
same-title disambiguation already handled by the `year` field in `entities`.

The open question is where it runs: server-side with debounce, or shipped to the client outright.
The `entities` map is a few MB and compresses well, which makes the client option real and would
remove the busiest endpoint from the server entirely. Worth deciding *before* the stack, since
"ship the index to the client" changes what the server is for.

---

## 5. Open questions needing answers

From [`ENGINE_CONFORMANCE.md`](ENGINE_CONFORMANCE.md) § Open questions:

| Question | Status |
|---|---|
| **Failure reason codes** | **Highest priority.** `RoundOver` cannot distinguish a repeat, a bad connection, a wrong type, a give-up, or a lapsed deadline. A match layer that penalizes them differently needs this, and it changes the `RoundOver` contract. |
| Opening player index | Needed for replay with attribution. |
| Deadline expiry ownership | Reduced by 018 to a reason-code question. |
| Exhausted frontier | **Measured** ([ADR 019](DECISIONS.md)) — rare. Not blocking; current behaviour defensible. |
| Chain length limits | A persistence and payload concern before an engine one. |

---

## 6. Known debt

| Item | Notes |
|---|---|
| [Issue #19](https://github.com/zws33/bacons_law/issues/19) — ETL query fidelity | Missing `?actor wdt:P31 wd:Q5`; documentary/TV-film exclusions leak. Needs a **full re-extract**, the expensive step — batch every query change into one rebuild and bump `QUERY_VERSION`. Not urgent: [ADR 019](DECISIONS.md) measured the confound at 0.02% of degree-1 actors. |
| [Issue #17](https://github.com/zws33/bacons_law/issues/17) — engine test coverage | Six behaviours implemented but untested. Absorbed by the conformance suite; land it during engine work, not before. |
| `:core` type reconciliation | Still `Int` / `Set<Int>` from the dropped TMDB source. Retyping to QID strings breaks eight call sites across `:backend` and `:app`. Only worth doing if Kotlin survives 3.1. |
| `:backend` | Still the TMDB proxy it started as. |

---

## 7. Suggested sequencing

Not a decision — a proposal, offered because the dependencies are real.

1. **Typeahead placement (4.2)** — decide first. If the index ships to the client, the server's job
   shrinks and 3.1 and 3.2 are both easier decisions.
2. **Stack (3.1)** — unblocks everything in the engine and match layer. Front-load it: it is the
   least reversible of the four, though the conformance spec keeps even this cheaper than it looks.
3. **Failure reason codes (5)** — a `RoundOver` contract change, so decide before the match layer
   is written, not after.
4. **Match layer spec (4.1)** — then the engine reconciliation and issue #17 fold into building it.
5. **Store and hosting (3.2, 3.3)** — genuinely deferrable. Both are now unconstrained, and neither
   blocks writing the engine or the match layer.

**What is not on the critical path:** issue #19's rebuild, `:app`, and `:backend`.
