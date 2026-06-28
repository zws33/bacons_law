# Kotlin/Android implementation — archived docs

This folder preserves the documentation for the **original Kotlin/Compose Android implementation**
of Bacon's Law. That implementation is a parallel showcase and lives on the **`main`** branch — its
code (`core/`, `app/`, `backend/` Gradle modules) is not present on this `fullstack-py-ts-rewrite`
branch.

These docs are kept verbatim for historical context. They are **superseded on this branch** by the
Python/TypeScript rewrite documentation:

| Archived (Kotlin) | Current (Python/TS) |
|---|---|
| [`ROADMAP.md`](ROADMAP.md) — Android phases | [`../../ROADMAP.md`](../../ROADMAP.md) |
| [`DECISIONS.md`](DECISIONS.md) — ADRs 001–007 | [`../DECISIONS.md`](../DECISIONS.md) — ADRs 008+ |
| [`GAME_SPEC.md`](GAME_SPEC.md) — original rules + product intent | [`../GAME_SPEC_V2.md`](../GAME_SPEC_V2.md) — engine spec |
| [`GAME_REPOSITORY_REFACTOR.md`](GAME_REPOSITORY_REFACTOR.md) — Android ViewModel/Repository plan | *(no equivalent — Android-specific)* |

The two implementations demonstrate different stacks and are free to diverge. Nothing here is
maintained against the current rewrite; treat it as a snapshot. For the current project's direction,
start at [`../PYTHON_TS_REWRITE_PLAN.md`](../PYTHON_TS_REWRITE_PLAN.md).
