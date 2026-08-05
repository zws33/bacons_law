# `:app` — Android client notes

> **Reference only, and provisional.** Built for the pass-the-phone, TMDB-backed design that has since
> been dropped. Don't modify it unless explicitly asked, and don't treat its use of `:core` as a
> constraint on the engine — it may be replaced by a new client (possibly not Android) at the planning
> session. See the root `AGENTS.md`.

Prefer Google's `android` CLI if on PATH (`android version || android --help`) for SDK install/update,
emulator/device workflows, project discovery, and official docs. Use Gradle for normal builds/tests.
If `android` is not installed, say so and fall back to the Gradle + Android SDK flow.
