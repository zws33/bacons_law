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
> **Amended 2026-08-13** for [`MATCH_CONFORMANCE.md`](MATCH_CONFORMANCE.md), now authoritative, which
> consumed §4.1 and one of §5's questions.
>
> **Amended 2026-08-14** for [ADR 025](DECISIONS.md), which consumed §3.1 and voided three of §6's
> five debt rows.
>
> **The deletion trigger has not fired.** Two decisions remain: **store (§3.2), hosting (§3.3)**.
> Nothing else in this file is outstanding. Delete it once those are made.

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

### 3.1 ~~Server language and framework~~ — **DECIDED, [ADR 025](DECISIONS.md)**

Resolved. **TypeScript on Node with Fastify, in a new top-level `server/` directory.** The Python ETL
is unaffected; `:core` and `:backend` are superseded rather than ported, and Kotlin leaves the running
system.

**Decided in two parts on different criteria.** The language was the one-way door and turned on
ecosystem and deployment; the runtime and framework are two-way doors — a framework swap is a
routing-layer rewrite in a codebase whose engine and match layer never see an HTTP type — and turned
on vendor-SDK compatibility and the boundary-validation and rate-limiting stories.

**The criteria this section listed did not separate the candidates.** Enumerating the server's actual
jobs found no throughput-, latency-, or concurrency-bound path, so ecosystem, expression, and
deployment carried the whole decision. Two of the listed criteria turned out to be worth less than
their placement suggested: ADR 021's static type-alternation criterion is mandatory at the HTTP
boundary in every language, and "Kotlin is already in the tree" amounts to 188 lines that the
conformance suite specifies as failing.

**Three facts from it bear on §3.2 and §3.3.** Bundled auth + store providers ship first-class
TypeScript SDKs, so §3.2 is unconstrained by this. ADR 018's
cold-start measurement transfers without re-measuring — every JavaScript runtime in play starts faster
than CPython — so §3.3 keeps scale-to-zero for free. And **edge/isolate runtimes are ruled out** for
§3.3 — the in-memory graph exceeds per-isolate memory limits, language-independently.

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

**Unconstrained by [ADR 025](DECISIONS.md):** the bundled auth + store providers all ship first-class
TypeScript SDKs, so the stack decision does not narrow this one.

### 3.3 Hosting

Open. Cold start is not an obstacle (§2), and [ADR 025](DECISIONS.md) keeps that true without a
re-measure — every JavaScript runtime in play starts faster than CPython. Decide on cost, operational
simplicity, and familiarity.

**Two inputs from [ADR 025](DECISIONS.md).** Edge and isolate runtimes are ruled out — the in-memory
graph exceeds per-isolate memory limits, language-independently — so the choice is among containers,
scale-to-zero included. And the graph's resident memory is unmeasured; that number has to exist before
an instance can be sized.

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

## 4. Specs that did not exist — both now written

### 4.1 ~~The match layer~~ — **WRITTEN, [`MATCH_CONFORMANCE.md`](MATCH_CONFORMANCE.md)**

Resolved. M1–M16 and a conformance suite, authoritative and language-agnostic. Every item this section
listed is specified: strike accounting, `LimitPolicy` (eliminate vs. end match), standings, mode
configuration, opener rotation, and cross-round exclusions under `reuse == Forbidden`.

**Two facts from it bear on decisions still open here.** A match is terminal
([M12](MATCH_CONFORMANCE.md#m12--every-match-terminates)), so terminal matches can be archived out of
the hot path — the one requirement the match layer places on §3.2. And the layer is pure, with five
functions and no clock, store, or graph, so it constrains §3.1 only through sealed unions
(`LimitPolicy`, `ReusePolicy`, `RemovalCause`) — a second data point for the static-enforcement
criterion, alongside the round engine's `Move`.

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
| ~~Opening player index~~ | **DECIDED, [ADR 024](DECISIONS.md) / [`MATCH_CONFORMANCE.md`](MATCH_CONFORMANCE.md).** Dissolved: the opener is always seat 0 ([M8](MATCH_CONFORMANCE.md#m8--the-round-roster-is-derived-never-stored)), so there is no index to record. Replay needs that round's *roster*, which [M9](MATCH_CONFORMANCE.md#m9--a-seat-index-is-round-local) derives from `Removal.beforeRound` plus a round-0 opener fixed at `matchOrder[0]`. |
| Exhausted frontier | **Measured** ([ADR 019](DECISIONS.md)) — rare. Not blocking; current behaviour defensible. |
| Chain length limits | A persistence and payload concern before an engine one. [ADR 021](DECISIONS.md)'s termination proof bounds the chain at ~95,000 moves, which does not help — it is a proof, not a usable cap. |

**Two obligations were added, not removed.** ADR 021 makes the round engine's termination guarantee
*joint*: the engine bounds the chain, and the session layer's deadline bounds the rejection retry loop.
[ADR 024](DECISIONS.md) adds a second: voiding the round in flight must be atomic with the withdrawal
that causes it, since a late result from a voided round is indistinguishable at the match layer from
the replacement round's. Both fall on whatever the session layer turns out to be, and neither existed
when this agenda was written.

---

## 6. Known debt

| Item | Notes |
|---|---|
| [Issue #19](https://github.com/zws33/bacons_law/issues/19) — ETL query fidelity | Missing `?actor wdt:P31 wd:Q5`; documentary/TV-film exclusions leak. Needs a **full re-extract**, the expensive step — batch every query change into one rebuild and bump `QUERY_VERSION`. Not urgent: [ADR 019](DECISIONS.md) measured the confound at 0.02% of degree-1 actors. |
| ~~[Issue #17](https://github.com/zws33/bacons_law/issues/17) — engine test coverage~~ | **Moot, [ADR 025](DECISIONS.md).** The six untested behaviours were `:core`'s, and `:core` is not ported. The conformance suite covers the replacement engine. Close the issue rather than tracking it. |
| ~~`:core` **behavioural** delta~~ | **Moot, [ADR 025](DECISIONS.md).** It described the cost of porting `:core` forward — an engine ported from it unchanged fails the whole of the suite's Group C. Nothing is ported, so the delta is never paid. The new engine is written against the spec directly. |
| ~~`:core` type reconciliation~~ | **Moot, [ADR 025](DECISIONS.md).** Its own condition was "only worth doing if Kotlin survives 3.1." It did not. |
| `:backend` | Still the TMDB proxy it started as, and now reference-only. Not debt — dead code awaiting a decision to delete it. |

---

## 7. Suggested sequencing

Not a decision — a proposal, offered because the dependencies are real. **Four of the original five
steps are done**, leaving only the fifth; what follows is the remainder, renumbered.

- ~~Typeahead placement~~ — **done, [ADR 020](DECISIONS.md)**. Note its stated rationale did not
  survive: it was sequenced first on the theory that shipping the index would shrink the server's job,
  and the server keeps the resolve endpoint either way. Deciding it first was still cheap and correct.
- ~~Failure reason codes~~ — **done, [ADR 021](DECISIONS.md)**, and out of order. It was slotted after
  the stack on the grounds that it is a `RoundOver` contract change; it turned out to be answerable
  from the round/match seam alone, with no stack input at all.
- ~~Client~~ — **done, [ADRs 022–023](DECISIONS.md)**, and it was never on this list. It was filed as
  §3.4, a decision with no sequencing position; it turned out to *unblock* the stack by removing a
  criterion from it, and to force an identity change along the way.
- ~~Match layer spec~~ — **done, [`MATCH_CONFORMANCE.md`](MATCH_CONFORMANCE.md)**, and the precedent
  held: it was sequenced behind the stack in case it needed one, and needed no stack input at all. Two
  rules were added while writing it that the commissioning entry did not anticipate —
  `Removal.beforeRound` and a fixed round-0 opener, without which an earlier round's roster is not
  recoverable and a stored result cannot be replayed with attribution.

- ~~Stack~~ — **done, [ADR 025](DECISIONS.md)**, and the criteria that made it look hard did not
  decide it. It was sequenced first as the least reversible decision left; that held, but the
  reversibility came from the two conformance specs rather than from the sequencing. A lesson worth
  keeping: it turned out to be *two* decisions of very different weight, and separating them was what
  let the reversible half be decided quickly and the irreversible half slowly.

1. **Store (3.2)** — coupled to ADR 022's deferred auth-provider choice, since some providers bundle
   the two. Weigh the bundle against the per-read pricing point in §3.2. ADR 025 does not narrow it:
   the bundled providers all ship first-class TypeScript SDKs.
2. **Hosting (3.3)** — genuinely deferrable, and constrained only by ADR 025's edge/isolate exclusion.

**What is not on the critical path:** issue #19's rebuild, `:app`, and `:backend`.

**Still true:** §1 and §2 are untouched by ADRs 020–025. §3's remaining two decisions are the bulk of
what the session has not done.
