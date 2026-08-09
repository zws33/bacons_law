# Planning session agenda

> **This is an INPUT to the planning session, not a roadmap and not a status document.**
> It exists to stop the session rediscovering what is already settled. It records no decisions of
> its own — every "open" item below is open precisely because nobody has decided it.
>
> **Delete this file once the session has produced its ADRs.** A consumed agenda that survives as
> a document is how a project ends up with two sources of truth. Nothing should ever link to it.
>
> Prepared 2026-08-06, after [ADR 018](DECISIONS.md) and [ADR 019](DECISIONS.md).
> **Amended 2026-08-09** for [ADR 020](DECISIONS.md) and [ADR 021](DECISIONS.md), which consumed
> §4.2 and two of §5's five questions. Resolved items are struck through and point at the ADR that
> settled them rather than being deleted, so that a reader who remembers the open question finds the
> answer instead of a silent gap — **the ADR is the source of truth in every case, never the summary
> here.** The file still records no decisions of its own.
>
> **The deletion trigger has not fired.** §3's four decisions — stack, store, hosting, client — are
> untouched, and they are now most of what is left. Delete this once they are made.

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

### 4.2 ~~The typeahead~~ — **DECIDED, [ADR 020](DECISIONS.md)**

Resolved. Typeahead resolves **server-side** against the in-memory `entities` map with a debounced
client; the client-side index is deferred behind a `suggest(prefix) -> Candidate[]` seam, its trigger
being playtest evidence that latency is felt. Folded search keys derive at boot, never in the ETL.
[ADR 021](DECISIONS.md) adds the filtering rule: by required type and the played set, never by
adjacency.

**Do not re-open on the sequencing argument this section originally made.** It claimed that shipping
the index to the client would shrink the server's job and make 3.1 and 3.2 easier. The server keeps the
resolve endpoint either way — it must re-resolve any submitted QID regardless — so those decisions are
unchanged by this one.

One dependent item is still live and is **not** a planning question: sitelink counts are needed for
result ranking and are currently dropped at `Edge`. Surfacing them is a `transform`+`emit` change
against existing raw partitions — no re-extract, independent of Issue #19. Batch it with the actor
disambiguator question if that is taken up.

---

## 5. Open questions needing answers

From [`ENGINE_CONFORMANCE.md`](ENGINE_CONFORMANCE.md) § Open questions:

| Question | Status |
|---|---|
| ~~Failure reason codes~~ | **DECIDED, [ADR 021](DECISIONS.md).** Largely dissolved rather than answered: repeat and wrong type turned out not to be round outcomes at all — they are *rejections*, leaving the round unchanged — and `Unconnected` is the only outcome `playMove` can now produce. The surviving give-up/lapse pair became a `ForfeitReason` parameter. |
| ~~Deadline expiry ownership~~ | **DECIDED, [ADR 021](DECISIONS.md).** Session layer adjudicates and calls `forfeit(state, DeadlineLapsed)`. Now carries an obligation instead: a rejected submission must not reset the deadline, which is the only bound on the retry loop. |
| Opening player index | Needed for replay with attribution. **Still open.** |
| Exhausted frontier | **Measured** ([ADR 019](DECISIONS.md)) — rare. Not blocking; current behaviour defensible. |
| Chain length limits | A persistence and payload concern before an engine one. [ADR 021](DECISIONS.md)'s termination proof bounds the chain at ~95,000 moves, which does not help — it is a proof, not a usable cap. |

**One question was added, not removed.** ADR 021 makes the round engine's termination guarantee
*joint*: the engine bounds the chain, and the session layer's deadline bounds the rejection retry loop.
That is a new obligation on whatever the session layer turns out to be, and it did not exist when this
agenda was written.

---

## 6. Known debt

| Item | Notes |
|---|---|
| [Issue #19](https://github.com/zws33/bacons_law/issues/19) — ETL query fidelity | Missing `?actor wdt:P31 wd:Q5`; documentary/TV-film exclusions leak. Needs a **full re-extract**, the expensive step — batch every query change into one rebuild and bump `QUERY_VERSION`. Not urgent: [ADR 019](DECISIONS.md) measured the confound at 0.02% of degree-1 actors. |
| [Issue #17](https://github.com/zws33/bacons_law/issues/17) — engine test coverage | Six behaviours implemented but untested. Absorbed by the conformance suite; land it during engine work, not before. |
| `:core` **behavioural** delta — grew with [ADR 021](DECISIONS.md) | Was "retype `Int` → QID strings, fix eight call sites." Now also: the prototype resolves every repeat and wrong-type submission to a **round loss**, which ADR 021 inverts to a rejection. An engine ported from `:core` unchanged fails the whole of the suite's Group C. The conformance spec's coverage map marks these `no` under *Implemented*, not merely untested. |
| `:core` type reconciliation | Still `Int` / `Set<Int>` from the dropped TMDB source. Only worth doing if Kotlin survives 3.1 — and if it does, fold it into the behavioural rewrite above rather than doing it separately. |
| `:backend` | Still the TMDB proxy it started as. |

---

## 7. Suggested sequencing

Not a decision — a proposal, offered because the dependencies are real. **Two of the original five
steps are done**; what follows is the remainder, renumbered.

- ~~Typeahead placement~~ — **done, [ADR 020](DECISIONS.md)**. Note its stated rationale did not
  survive: it was sequenced first on the theory that shipping the index would shrink the server's job,
  and the server keeps the resolve endpoint either way. Deciding it first was still cheap and correct.
- ~~Failure reason codes~~ — **done, [ADR 021](DECISIONS.md)**, and out of order. It was slotted after
  the stack on the grounds that it is a `RoundOver` contract change; it turned out to be answerable
  from the round/match seam alone, with no stack input at all.

1. **Stack (3.1)** — now the front of the queue and the least reversible decision left. The conformance
   spec keeps it cheaper than it looks, and it has grown slightly more opinionated:
   [ADR 021](DECISIONS.md) lets type alternation be enforced statically (MAY, not MUST), which favours
   languages with closed sum types. The spec phrases it as optional precisely so this does not decide
   the stack by the back door.
2. **Match layer spec (4.1)** — unblocked now that reason codes exist. `RoundEndReason` is the
   vocabulary its penalty table is written against. The `:core` rewrite and issue #17 fold into
   building it.
3. **Store and hosting (3.2, 3.3)** — genuinely deferrable. Both unconstrained; neither blocks the
   engine or the match layer.
4. **Client (3.4)** — unchanged, still coupled to push via ADR 013's device-anchored identity.

**What is not on the critical path:** issue #19's rebuild, `:app`, and `:backend`.

**Still true, and now the main reason this file exists:** §1, §2, and §3 are untouched by ADRs 020 and
021. The four decisions in §3 are the bulk of what the session has not done.
