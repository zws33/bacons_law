# Decision Log

Lightweight ADR-style record of key technical and product decisions.

---

## 001: MVP is pass-the-phone two-player, not solo chain-building

**Date:** 2026-03-19

**Context:** The core fun of the game is being *quizzed* — prompted with a movie or actor and having to prove you know a connection. A solo chain-building mode where you browse and select freely lacks the reactive, unpredictable element that makes the game engaging.

**Decision:** MVP is a two-player, pass-the-phone game where the other player's choices create the unpredictability. The app validates moves, it doesn't generate prompts.

**Consequences:** Requires two people physically present to play. Single-player "quiz-master" mode (app as prompter) is a future enhancement, not the starting point.

---

## 002: Android/Kotlin/Compose for MVP client

**Date:** 2026-03-19

**Context:** Evaluated building the MVP as a Go backend + web frontend (for T-shape learning) vs. an Android app (fastest to ship). The existing repo has Kotlin/Compose code and TMDB integration.

**Decision:** Ship the MVP as an Android app. Go enters the picture as the multiplayer backend in a later phase, where it actually earns its keep (concurrent sessions, WebSockets, lightweight deployment).

**Rationale:** Pass-the-phone is inherently a mobile interaction. Android is the fastest path to a playable game. Go's learning value is in server-side concurrency, not in reimplementing a game engine that already works in Kotlin.

**Consequences:** Go learning is deferred, not abandoned. It becomes the multiplayer backend tech in a future phase.

---

## 003: Strip MVP game mechanics to the core quiz loop

**Date:** 2026-03-19

**Context:** A prior brainstorming plan proposed passes, challenges, miss tolerance, time limits, elimination/continuous scoring modes, table vetoes, and obscurity sliders — all before shipping.

**Decision:** MVP has none of these. The game loop is: select a connection, app validates, pass the phone. First invalid move loses. That's it.

**Rationale:** Every mechanic added before shipping is a mechanic you're guessing players want. Ship the core loop, play 10 rounds, then add what's actually missing based on real experience.

**Consequences:** The game may feel thin at first. That's acceptable — it's faster to add mechanics to a shipped game than to balance them in a vacuum.

---

## 004: Existing codebase is a starting point, not sacred

**Date:** 2026-03-19

**Context:** The existing repo has a Kotlin game engine (`:core`), Compose UI with TMDB search, and a multi-module architecture. The game engine models two-player alternation with move validation. The UI has search but isn't connected to the game logic.

**Decision:** Use the existing code as a starting point — especially the TMDB integration and project structure — but rewrite or restructure freely where it doesn't serve the MVP.

**Rationale:** The existing code amounts to a few days of work. Preserving it for sunk-cost reasons would constrain design decisions. The TMDB API integration and Retrofit setup are genuinely reusable; the game state machine may need reworking to match the refined spec.

**Consequences:** Need to evaluate the existing `:core` game engine against the game spec. It may map cleanly, or it may be simpler to rewrite with the spec as the guide.
