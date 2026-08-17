# Agents Guide — Bacon's Law

A trivia game based on "Six Degrees of Kevin Bacon." Two or more players on separate devices take
turns naming movies and actors to build a chain of connections, each answer connecting factually to
the one before it. Play is **correspondence** — async, move-when-you-can, with a per-turn deadline. A
server owns authoritative game state and validates every move against a precomputed actor↔movie graph
held in Postgres alongside that state.

> **This file is navigation, not rules.** It holds repository layout, build commands, environment, and
> conventions — the things that are true every session and change rarely.
>
> **Domain rules, architecture decisions, and scope live in the documents indexed under
> [Where the rules live](#where-the-rules-live).** Read them there. Do not expect a summary of them
> here, and when a rule changes, change it in the document that owns it — a second copy in this file
> is how the two drift apart.

> **`etl/` is the only durable source code and the only fixed contract.** No Kotlin in this repo is
> live code any more: the server is TypeScript on Node ([ADR 025](docs/DECISIONS.md)), and neither
> `:core` nor `:backend` is ported forward. All three Kotlin modules are **reference only — do not
> modify unless explicitly asked.** Never preserve a signature, module layout, or design decision
> merely because it is already in the tree.
>
> **The system to be built is not in the tree yet:** a `server/` directory
> ([ADR 025](docs/DECISIONS.md)) and a web client directory ([ADR 023](docs/DECISIONS.md)). Neither is
> started. Storage is Supabase Postgres and the graph lives in it, not in the server's memory
> ([ADRs 026 and 027](docs/DECISIONS.md)); hosting is the one decision still open.
>
> **Prior efforts are preserved as reference, not maintained** — the Kotlin/Compose Android client
> (`:app`) and the Python/FastAPI showcase (branch `fullstack-py-ts-rewrite`, tag
> `python-fastapi-showcase`). [docs/HISTORY.md](docs/HISTORY.md)
> records what they were and why they ended; their detailed plans were deleted, so do not go looking.
>
> There is currently **no roadmap document and no architecture-orientation skill** — both were retired
> pending regeneration after the planning session. Do not infer phase or status from any file.

---

## Repository layout

The repo root is intentionally **stack-agnostic** — shared docs and meta only. Each component is a
**self-contained project in its own top-level directory** with its own toolchain. Adding a polyglot
experiment is *adding a directory*, not restructuring the root.

| Path | What it is | Status |
|---|---|---|
| `etl/` | Offline Wikidata graph build (Python, `uv`/`ruff`). Produces the versioned artifact everything else is written against. Own rules in [etl/AGENTS.md](etl/AGENTS.md) | **Durable.** The one fixed contract |
| `server/` | The session server — TypeScript on Node, Fastify ([ADR 025](docs/DECISIONS.md)). Holds the round engine, the match layer, the session layer, and the loader that populates Postgres from the ETL artifact ([ADR 026](docs/DECISIONS.md)) | **Not started.** Where new server work goes |
| *(unnamed)* | The web client — the primary client ([ADR 023](docs/DECISIONS.md)), a **separate top-level directory** with its own toolchain | Not started |
| `kotlin/core` (`:core`) | The pure round engine prototype. Superseded by ADR 025 and not ported; the spec it was graded against, [docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md), outlives it | **Reference only — do not modify** |
| `kotlin/backend` (`:backend`) | Still the thin TMDB proxy it started as. Never became the session server | **Reference only — do not modify** |
| `kotlin/app` (`:app`) | Compose Android client for the retired pass-the-phone model | **Reference only — do not modify.** Not the starting point for any future client |

Gradle commands run from `kotlin/` — that is where `settings.gradle.kts` and the wrapper live. Module
notation (`:core`, `:backend`, `:app`) is relative to that project. `:backend` and `:app` both depend
on `:core`; `:core` depends on neither. **Nothing there is under active development.**

---

## Build & test

The ETL runs from `etl/`. **No build tooling runs from the repo root**, and none will — `server/` and
the web client each get their own.

Gradle still runs from `kotlin/`, but only to build reference code. `./gradlew :core:jvmTest` was the
feedback loop for game logic and no longer is; `:core` is a KMP module (`commonMain` / `jvmTest`), so
there is **no `:core:test` task**.

---

## Environment

There is no TMDB key and no API key of any kind — validation data is CC0 Wikidata, built offline.

- **ETL** runs offline; its Wikidata access needs no secret.
- **Server** talks to Supabase ([ADR 027](docs/DECISIONS.md)) and needs a Postgres connection string
  and a service key, plus the provider's JWKS URL for token verification. It also needs a credential
  for a **separate transactional-email provider** ([ADR 029](docs/DECISIONS.md)) — game notifications
  do not go through Supabase Auth's mailer. Inject all four from the environment; never commit them.
  The service key is server-only — clients never reach the database.

---

## Conventions

- **Commits:** Conventional commit format — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **TypeScript (`server/`, web client):** pure functions and immutable data in the engine and match
  layer. Exhaustiveness over discriminated unions is checked with a `never` default, not assumed.
  Untyped input is validated at the HTTP boundary — normative, per [ADR 025](docs/DECISIONS.md).
- **Python (`etl/`):** keep it self-contained and offline.
- **Kotlin (`kotlin/`):** reference only. Don't add to it. `gradle/libs.versions.toml` still owns its
  version strings.

---

## Where the rules live

Specs are authoritative and this file defers to them. ADRs record reasoning — read them for *why*.
021–027 are commitments from the planning session; earlier ADRs are reasoned positions that several
of those have since overtaken. **Where an ADR has been overtaken it says so inline at the top** — read
that marker before acting on its contents rather than treating any range as wholesale provisional.

**Read the relevant document before changing behavior in its area.** These are not summaries to be
skimmed; each one carries rules that are not obvious and that have already been argued once.

| Document | Owns |
|----------|------|
| [docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md) | **The round-engine spec of record.** Move validation, turn rotation, repeats, the opening move, rejections vs. round losses, termination. Rules R1–R17 + a numbered conformance suite; language-agnostic. Authoritative over `kotlin/core/.../GameEngine.kt` and its tests, which are prototype code it records the divergences from |
| [docs/MATCH_CONFORMANCE.md](docs/MATCH_CONFORMANCE.md) | **The match-layer spec of record** ([ADR 024](docs/DECISIONS.md)). Strikes, removal from play, match end, standings, opener rotation, cross-round exclusions. Rules M1–M16 + a numbered conformance suite; language-agnostic. Nothing implements it yet |
| [docs/DECISIONS.md](docs/DECISIONS.md) | **The ADR log — and the project's scope.** Architecture, data source, transport, identity, client, typeahead, and what is deliberately *not* being built. **Read [ADR 026](docs/DECISIONS.md) before anything in 009, 011, or 018 about where the graph lives or what the server holds in memory**, and **[ADR 018](docs/DECISIONS.md) before anything in 008–012 about transport, presence, or modes.** Its closing **Open: Hosting** section is the one decision still open and carries the constraints bearing on it. Check it before adding any game mechanic |
| [etl/AGENTS.md](etl/AGENTS.md) | ETL operating rules and the load-bearing facts of the graph build — including what the cast cap does to "appeared in" |
| [etl/README.md](etl/README.md) | The artifact's current shape, how to verify one, and the ETL's deferred follow-ons |
| `movie-actor-chain-game` skill | Domain rules and vocabulary. Implementation-agnostic — it deliberately leaves repeats, the opening move, and "appeared in" policy open, and the conformance specs answer them |
| [docs/investigations/](docs/investigations/) | **Records, never rules.** Write-ups and retrospectives containing falsified hypotheses by design. Non-normative *by location* — never cite one as authority. Binding outcomes were promoted out into an ADR or a spec; cite that instead. Read [its README](docs/investigations/README.md) first |
| [docs/HISTORY.md](docs/HISTORY.md) | The two prior efforts — what they were, why they ended, where the code lives. Reference only; neither is guidance |
