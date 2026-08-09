# Planning session agenda

> **This is an INPUT to the planning session, not a roadmap and not a status document.**
> It exists to stop the session rediscovering what is already settled. It records no decisions of
> its own — every "open" item below is open precisely because nobody has decided it.
>
> **Delete this file once the session has produced its ADRs.** A consumed agenda that survives as
> a document is how a project ends up with two sources of truth. Nothing should ever link to it.
>
> Prepared 2026-08-06, after [ADR 018](DECISIONS.md) and [ADR 019](DECISIONS.md).
> **Amended 2026-08-09** for [ADR 020](DECISIONS.md), [ADR 021](DECISIONS.md),
> [ADR 022](DECISIONS.md) and [ADR 023](DECISIONS.md), which consumed §3.4, §4.2, and two of §5's five
> questions. Resolved items are struck through and point at the ADR that settled them rather than
> being deleted, so that a reader who remembers the open question finds the answer instead of a silent
> gap — **the ADR is the source of truth in every case, never the summary here.** The file still
> records no decisions of its own.
>
> **The deletion trigger has not fired**, but it is close. Three decisions remain: **stack (§3.1),
> store (§3.2), hosting (§3.3)** — plus the match-layer spec (§4.1), which is a writing task rather
> than a decision. Delete this file once those three are made.

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

**Criteria, post-018 and post-023:** ecosystem and library maturity; how cleanly the language expresses
the round engine's sealed-union state machine (`Move = Actor | Movie`, exhaustive matching); deployment
simplicity; and familiarity. ~~Whether types can be shared with the client~~ — **struck by
[ADR 023](DECISIONS.md)**: the client is decoupled, and a client cannot run the connection check
regardless, because that needs the graph.

**Added by [ADR 021](DECISIONS.md):** whether you want type alternation enforced *statically*. The spec
permits it (MAY, not MUST) and it favours languages with closed sum types. Phrased as optional
precisely so it does not decide this by the back door — but if you want it, it is a criterion.

**Removed by [ADR 023](DECISIONS.md):** single-language velocity. Stated explicitly alongside the
client decision — a mix of languages is acceptable where it suits the project's goals, and
TypeScript/JavaScript, Kotlin, Java, and Python are all comfortable. "One language end to end" is not
an argument here in either direction.

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

**Sharpened by [ADR 022](DECISIONS.md):** that read imbalance has a price tag. A ~2s poll loop is a
read generator by construction, so a store billing **per read** converts the notification design into
a running cost while a store on a fixed instance does not. Structural, not a tuning detail.

**Newly coupled:** several providers bundle auth with storage, so this may be one decision with ADR
022's deferred provider choice rather than two. Weigh the bundling against the per-read point above —
they can pull in opposite directions.

### 3.3 Hosting

Fully open. Cold start is not an obstacle (§2). Decide on cost, operational simplicity, and
familiarity.

### 3.4 ~~Client~~ — **DECIDED, [ADR 023](DECISIONS.md)**

Resolved. **Web is the primary client** and the one real users get; native clients are follow-ups
built primarily to demonstrate capability, with no app-store deployment until traction justifies the
cost. The stated reason: web is the easiest way to reach real users, and the app-store deployment
process is not worth navigating before there is evidence anyone wants the game.

**The constraint this section raised turned out to run the other way.** It flagged that device-anchored
push couples the client to notification design. True — but the resolution was to change the identity
model, not the client: [ADR 022](DECISIONS.md) supersedes ADR 013. **The notification channel itself is
now reopened rather than settled** — identity is no longer a device, so ADR 018's push-token addressing
no longer applies, and ADR 022 leaves the replacement undecided.

**Consequence for §3.1 — this section is no longer an input to the stack.** Client language is
decoupled, auth is provider-issued JWTs verifiable in any ecosystem, and a client cannot run the
connection check anyway because that needs the 21 MB graph. **"Whether types can be shared with the
client" should be struck from §3.1's criteria** — it was doing more work there than it could support.

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

Not a decision — a proposal, offered because the dependencies are real. **Three of the original five
steps are done**; what follows is the remainder, renumbered.

- ~~Typeahead placement~~ — **done, [ADR 020](DECISIONS.md)**. Note its stated rationale did not
  survive: it was sequenced first on the theory that shipping the index would shrink the server's job,
  and the server keeps the resolve endpoint either way. Deciding it first was still cheap and correct.
- ~~Failure reason codes~~ — **done, [ADR 021](DECISIONS.md)**, and out of order. It was slotted after
  the stack on the grounds that it is a `RoundOver` contract change; it turned out to be answerable
  from the round/match seam alone, with no stack input at all.
- ~~Client~~ — **done, [ADRs 022–023](DECISIONS.md)**, and it was never on this list. It was filed as
  §3.4, a decision with no sequencing position; it turned out to *unblock* the stack by removing a
  criterion from it, and to force an identity change along the way.

1. **Stack (3.1)** — the front of the queue and the least reversible decision left. Now easier than
   when this agenda was written: the client no longer constrains it at all (§3.4). Two criteria moved —
   shared types struck, static type-alternation enforcement added.
2. **Match layer spec (4.1)** — unblocked now that reason codes exist. `RoundEndReason` is the
   vocabulary its penalty table is written against. The `:core` rewrite and issue #17 fold into
   building it. **Worth noting the precedent:** reason codes were expected to need the stack and did
   not. Check whether this one does before sequencing it behind §3.1.
3. **Store (3.2)** — now partly coupled to ADR 022's deferred auth-provider choice, since some
   providers bundle the two. Weigh the bundle against the per-read pricing point in §3.2.
4. **Hosting (3.3)** — genuinely deferrable and unconstrained.

**What is not on the critical path:** issue #19's rebuild, `:app`, and `:backend`.

**Still true:** §1 and §2 are untouched by ADRs 020–023. §3's remaining three decisions are the bulk of
what the session has not done.
