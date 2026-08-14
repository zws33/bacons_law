# Agents Guide — Bacon's Law

A trivia game based on "Six Degrees of Kevin Bacon." Two or more players on separate devices take
turns naming movies and actors to build a chain of connections, each answer connecting factually to
the one before it. Play is **correspondence** — async, move-when-you-can, with a per-turn deadline. A
server owns authoritative game state and validates every move against a precomputed actor↔movie graph
held in memory.

> **This file is navigation, not rules.** It holds repository layout, build commands, environment, and
> conventions — the things that are true every session and change rarely.
>
> **Domain rules, architecture decisions, and scope live in the documents indexed under
> [Where the rules live](#where-the-rules-live).** Read them there. Do not expect a summary of them
> here, and when a rule changes, change it in the document that owns it — a second copy in this file
> is how the two drift apart.

> **`etl/` is the only durable source code and the only fixed contract.** Everything else in this
> repo — `:core`, `:backend`, `:app`, and the application/server design in `docs/DECISIONS.md` — is
> **provisional**: the application build-out will be reevaluated in a planning session, stack
> included. Never preserve a signature, module layout, or design decision merely because it is already
> in the tree.
>
> **Prior efforts are preserved as reference, not maintained** — do not modify unless explicitly
> asked: the Kotlin/Compose Android client (`:app`) and the Python/FastAPI showcase (branch
> `fullstack-py-ts-rewrite`, tag `python-fastapi-showcase`). [docs/HISTORY.md](docs/HISTORY.md)
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
| `kotlin/core` (`:core`) | The pure round engine — round state machine, no platform or I/O dependencies | Provisional prototype. Spec: [docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md) |
| `kotlin/backend` (`:backend`) | Still the thin TMDB proxy it started as. The graph-backed session server has not been built | Provisional; whether it is built here, or in Kotlin, is open |
| `kotlin/app` (`:app`) | Compose Android client for the retired pass-the-phone model | **Reference only — do not modify.** Not the starting point for any future client |
| *(none yet)* | The web client is decided ([ADR 023](docs/DECISIONS.md)) and will be a **new top-level directory**, not part of `kotlin/` | Not started |

Gradle commands run from `kotlin/` — that is where `settings.gradle.kts` and the wrapper live. Module
notation (`:core`, `:backend`, `:app`) is relative to that project. `:backend` and `:app` both depend
on `:core`; `:core` depends on neither.

---

## Build & test

Gradle runs from `kotlin/`; the ETL runs from `etl/`. **No build tooling runs from the repo root.**

`./gradlew :core:jvmTest` is the fast feedback loop for game logic. Note the target: `:core` is a KMP
module (`commonMain` / `jvmTest`), so there is **no `:core:test` task**; `allTests` runs every target.

---

## Environment

There is no TMDB key and no API key of any kind — validation data is CC0 Wikidata, built offline.

- **ETL** runs offline; its Wikidata access needs no secret.
- **Server** storage dependencies are undecided, so there are no environment variables to document
  yet. Whatever is chosen, inject credentials from the environment; never commit them.

---

## Conventions

- **Commits:** Conventional commit format — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **Kotlin:** follow existing style; prefer pure functions and immutable data in `:core`.
- **Build versions:** declared in `gradle/libs.versions.toml`. Don't hardcode version strings.
- **Python (`etl/`):** keep it self-contained and offline.

---

## Where the rules live

Specs are authoritative and this file defers to them. ADRs record reasoning — read them for *why*, and
treat 008–020 as reasoned positions the planning session may replace, not as commitments.

**Read the relevant document before changing behavior in its area.** These are not summaries to be
skimmed; each one carries rules that are not obvious and that have already been argued once.

| Document | Owns |
|----------|------|
| [docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md) | **The round-engine spec of record.** Move validation, turn rotation, repeats, the opening move, rejections vs. round losses, termination. Rules R1–R17 + a numbered conformance suite; language-agnostic. Authoritative over `kotlin/core/.../GameEngine.kt` and its tests, which are prototype code it records the divergences from |
| [docs/MATCH_CONFORMANCE.md](docs/MATCH_CONFORMANCE.md) | **The match-layer spec of record** ([ADR 024](docs/DECISIONS.md)). Strikes, removal from play, match end, standings, opener rotation, cross-round exclusions. Rules M1–M16 + a numbered conformance suite; language-agnostic. Nothing implements it yet |
| [docs/DECISIONS.md](docs/DECISIONS.md) | **The ADR log — and the project's scope.** Architecture, data source, transport, identity, client, typeahead, and what is deliberately *not* being built. **Read [ADR 018](docs/DECISIONS.md) first**; it amends 008, 011, and 012 on transport, hosting, and modes. Check it before adding any game mechanic |
| [etl/AGENTS.md](etl/AGENTS.md) | ETL operating rules and the load-bearing facts of the graph build — including what the cast cap does to "appeared in" |
| [docs/PLANNING_AGENDA.md](docs/PLANNING_AGENDA.md) | Open decisions, known debt, and what is already settled. The current state of play |
| `movie-actor-chain-game` skill | Domain rules and vocabulary. Implementation-agnostic — it deliberately leaves repeats, the opening move, and "appeared in" policy open, and the conformance specs answer them |
| [docs/investigations/](docs/investigations/) | **Records, never rules.** Write-ups and retrospectives containing falsified hypotheses by design. Non-normative *by location* — never cite one as authority. Binding outcomes were promoted out into an ADR or a spec; cite that instead. Read [its README](docs/investigations/README.md) first |
| [docs/HISTORY.md](docs/HISTORY.md) | The two prior efforts — what they were, why they ended, where the code lives. Reference only; neither is guidance |
