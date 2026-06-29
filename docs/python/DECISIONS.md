# Decision Log — Python/FastAPI showcase (archived)

> **Archived snapshot.** This is the decision log from the `fullstack-py-ts-rewrite`
> Python/FastAPI showcase (code on that branch, tagged `python-fastapi-showcase`). It is preserved
> for reference and is **not** maintained. The canonical, going-forward decision log for the trunk
> is [`../DECISIONS.md`](../DECISIONS.md). ADR 008 below is Python-specific. ADR 009's *substance*
> (multi-device, server-authoritative play) carries forward to the trunk and is re-expressed there
> in Kotlin terms; this version is kept as the original Python-framed record.

---

## 008: Package barrel imports are a convention, enforced by review — not tooling

**Date:** 2026-06-26

**Context:** Unlike Kotlin (`internal`), Java (package-private), or TypeScript (`export`), Python has no language-enforced module privacy. Every submodule is importable from anywhere, and `__all__` only governs `from module import *` — it does not prevent a caller from reaching past a package's `__init__.py` into its internal modules. The Python server (Phase 2) introduced package barrels (`app.models` re-exports its public types via `__init__.py`), but nothing distinguished "import the package's public surface" from "reach into its internals." `app/tmdb_client.py` and `tests/api/conftest.py` had drifted into deep imports (`from app.models.tmdb import ...`), bypassing the barrel.

**Options considered:**
1. Enforce with a ruff `flake8-tidy-imports` `banned-api` rule (TID251) denylisting `app.models.tmdb`, with a per-file-ignore for the barrel itself.
2. Enforce with `import-linter` contract-based rules.
3. Document the convention and enforce by code review; fix the existing deep imports by hand.

**Decision:** Option 3. The convention: a **cross-package consumer imports from the package barrel** (`from app.models import X`); a module imports a **sibling within its own package directly** (`from app.models.tmdb import X` is allowed only inside `app/models/`). It is enforced by convention and code review, not by a linter. The two existing deep imports were corrected to go through the barrel.

**Rationale:** A package's barrel re-exports are its contract; deep imports couple callers to internal file layout, so renaming or splitting a submodule breaks unrelated code. That cost is real, but the `banned-api` rule that would prevent it is a hand-maintained denylist — one entry per protected submodule, with no general "barrel-only" rule available in the Python ecosystem. At solo hobby scale, a denylist that grows with every new module costs more than the bug it prevents, and `app/models/` currently has a single submodule, so the rule would guard almost nothing. The documented convention plus review is sufficient teeth here. This is a discipline Python requires that compiled languages with enforced module privacy provide for free — naming it explicitly is the point of this entry.

**Consequences:**
- Phase 3's new packages (`store`, `ws`) follow the same rule: external code consumes them through their barrels; their internal modules import siblings directly.
- If an *architectural* boundary later warrants enforced teeth — most importantly keeping the engine pure (`app.engine` must never import `app.store` or `app.ws`) — reach for `import-linter` with a contract-based rule rather than growing a per-path `banned-api` denylist. That boundary, not barrel hygiene, is where automated enforcement would actually pay off.

---

## 009: Multi-device play is a core requirement of the rewrite; pass-the-phone was the local-only MVP

**Date:** 2026-06-28

**Supersedes the product framing of:** [Kotlin ADR 001](../DECISIONS.md#001-mvp-is-pass-the-phone-two-player-not-solo-chain-building) (pass-the-phone is no longer the end state — it was the original single-device MVP).

**Context:** The Kotlin-era ADR 001 framed the product as a two-player, pass-the-phone game on a single device, with remote multiplayer deferred to a later phase. The full-stack Python/TypeScript rewrite (branch `fullstack-py-ts-rewrite`) changes the goal: **multiple devices connect to the same room over the network**, and the backend owns authoritative game state. Server-authoritative state, WebSocket sessions, and a Redis-backed room store exist *to serve multi-device play* — that is the reason the server is being built, not an incidental later add-on. This needs to be stated explicitly because the stale single-device framing misleads design decisions — most concretely, it makes the room store's concurrency model look like a non-problem ("only one device, turns are sequential") when in fact two devices can send near-simultaneous messages to the same room.

**Decision:** Multi-device play is a core requirement of the rewrite, not a deferred enhancement. The backend is the authoritative owner of game state (the inversion anticipated in [Kotlin ADR 007](../DECISIONS.md#007-gameviewmodel-owns-game-state-for-phase-1-client-thins-in-phase-4)); clients submit move *intents* over a WebSocket and render the state the server pushes back. Turns remain sequential as a game rule, but turn-validation and state-mutation must be atomic *together* on the server, because sequential turns are a rule the server enforces — not a guarantee that only one message arrives at a time.

**Rationale:** The entire point of moving game logic to a server is to let separate devices share a room. Documenting pass-the-phone as the product actively undermines the work in progress — it was the reason an earlier review of the room store reasoned about concurrency as if it didn't matter.

**Consequences:**
- **Multi-device (clients) is distinct from multi-instance (servers).** N devices on one room is a client-count concern; M backend processes is a load concern. A *single* backend instance can hold thousands of WebSocket connections across thousands of rooms, so multi-device does **not** by itself require horizontal scaling.
- **Single instance + per-room `asyncio.Lock` is sufficient for multi-device.** Even on one process, asyncio interleaves coroutines at every `await`, so concurrent moves to the same room must be serialized — the in-process per-room lock does this. This is the Phase 3 design.
- **Horizontal scaling is deferred and comes as a pair.** Multiple instances break *both* the in-process lock (coordination must move to Redis — `WATCH`/`MULTI`/`EXEC` or a distributed lock) *and* in-memory broadcast (a second instance can't see the first's sockets — needs Redis Pub/Sub). These are a package: store-level atomicity without cross-instance broadcast yields correct state with silently broken fan-out. Build both or neither.
- **The deployment is a single long-lived instance by design**, not as a temporary workaround. Hosting is [Fly.io, not Cloud Run](PYTHON_TS_REWRITE_PLAN.md) precisely because persistent WebSocket connections and in-process session state are incompatible with scale-to-zero / multi-instance autoscaling. The single instance makes the `asyncio.Lock` authoritative; revisit `WATCH` + Pub/Sub only if real load ever justifies horizontal scaling (explicitly out of scope for this initiative).
