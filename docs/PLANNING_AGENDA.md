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
> five debt rows; then for [ADRs 026 and 027](DECISIONS.md), which consumed §3.2 and **struck an item
> from §1** — the first time a "do not re-litigate" entry has been overturned rather than confirmed.
>
> **The deletion trigger has not fired.** One decision remains: **hosting (§3.3)**, and ADR 026 hands
> it a binding constraint it did not have. Nothing else in this file is outstanding. Delete it once
> that is made.

---

## 1. Settled — do not re-litigate

These follow from the ETL contract and hold across any rewrite in any language. Discarding one
discards the reason `etl/` exists.

- Validation data is **precomputed offline** into a versioned artifact. No per-turn external API
  call, ever. *(Where it is loaded **to** changed — see [ADR 026](DECISIONS.md) — but that it is built
  once, offline, did not.)*
- ~~**Validation is co-located with the graph, in-process.** The engine/data seam must never cross a
  network hop.~~ **Overturned, [ADR 026](DECISIONS.md).** The graph lives in Postgres with game
  state; the seam crosses a network hop deliberately. This item did not belong in this list: every
  other entry follows from the ETL contract, and this one followed from a latency assumption
  [ADR 018](DECISIONS.md) and [ADR 025](DECISIONS.md) had already dismantled.
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
TypeScript SDKs, so §3.2 is unconstrained by this — borne out, [ADR 027](DECISIONS.md). ADR 018's
cold-start measurement transfers without re-measuring — every JavaScript runtime in play starts faster
than CPython — so §3.3 keeps scale-to-zero for free. And **edge/isolate runtimes are ruled out** for
§3.3 — the in-memory graph exceeds per-isolate memory limits, language-independently. *(That third
fact lasted one decision: [ADR 026](DECISIONS.md) took the graph out of memory. Not being reopened —
see §3.3.)*

### 3.2 ~~Durable store~~ — **DECIDED, [ADRs 026 and 027](DECISIONS.md)**

Resolved, and it turned out to be two decisions rather than one. **[ADR 026](DECISIONS.md): the store
is Postgres, and the graph moves into it** alongside game state — superseding ADR 009's in-process
clause and striking §1's co-location item. **[ADR 027](DECISIONS.md): Supabase** provides that
Postgres and, bundled with it, ADR 022's deferred identity provider.

**The section's own framing is what settled it.** The per-read point above ("structural, not a tuning
detail") was recorded as a criterion; adding a 456,129-row graph to the same store promotes it to
disqualifying, which excluded the document stores outright. The "newly coupled" note was correct — it
was one vendor decision, not two.

**What this section did not anticipate:** that the graph's placement was on the table at all. It was
filed under §1 as settled. Removing the latency justification is what reopened it.

### 3.3 Hosting

Open — **the last decision on this agenda.** Cold start is not an obstacle (§2), and
[ADR 025](DECISIONS.md) keeps that true without a re-measure. Decide on cost, operational simplicity,
and familiarity.

**Now constrained by [ADR 026](DECISIONS.md): the server must run in the same region as the Supabase
project.** Typeahead is the only human-perceptible latency budget in the system and now takes a
database round trip — same-region is ~1–3 ms and is noise, cross-region is 50–150 ms against an
estimated 200–400 ms p50. This narrows the candidate set more than any other input here.

**Two inputs this section used to carry are gone.** The edge/isolate exclusion lost its premise — the
graph is no longer resident — and is deliberately not being reopened, since Fastify is Node-first.
The graph's resident memory is no longer a number to measure before sizing; the instance can be small.

**Open cost input:** Supabase free-tier projects pause after inactivity, and a quiet week is normal
for correspondence play. Verify current terms against the paid tier before sizing the bill.

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

Resolved. Typeahead resolves **server-side** with a debounced client; the client-side index is
deferred behind a `suggest(prefix) -> Candidate[]` seam, its trigger being playtest evidence that
latency is felt. [ADR 021](DECISIONS.md) adds the filtering rule: by required type and the played
set, never by adjacency.

**Amended by [ADR 026](DECISIONS.md) in two places.** The corpus is a Postgres table rather than an
in-memory map, so folded keys derive **at load** rather than at boot — still server-side, still not in
the ETL, and still one TypeScript fold covering both corpus and query. And this section's own
framing — that typeahead searches the full corpus and never the legal moves — is what made the move to
SQL clean, because it means the search path never touches an edge.

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

Not a decision — a proposal, offered because the dependencies are real. **All five of the original
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

- ~~Store~~ — **done, [ADRs 026–027](DECISIONS.md)**, and it was the largest decision on this agenda,
  which nothing here predicted. It was listed as a vendor choice; it turned out to contain an
  architectural one, because asking what the store should hold reopened where the graph lives. The
  coupling this list flagged (bundled auth) was real and resolved as predicted. The lesson from the
  stack entry repeated: two decisions of different weight, separated.

1. **Hosting (3.3)** — the last item, and no longer unconstrained. ADR 026 requires the server to run
   in the same region as the Supabase project, which is a sharper constraint than the edge/isolate
   exclusion it replaces. Decide on cost and operational simplicity; verify the free tier's inactivity
   pause first.

**What is not on the critical path:** issue #19's rebuild, `:app`, and `:backend`.

**No longer true:** §1 is *not* untouched. [ADR 026](DECISIONS.md) struck its co-location item — the
only "do not re-litigate" entry this session overturned, and it went because it rested on a latency
assumption rather than on the ETL contract that justifies the rest of the list.
