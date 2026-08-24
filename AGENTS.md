# Agents Guide — Bacon's Law

A trivia game based on "Six Degrees of Kevin Bacon." Two or more players on separate devices take
turns naming movies and actors to build a chain of connections, each answer connecting factually to
the one before it. Play is **correspondence** — async, move-when-you-can, with a per-turn deadline. A
server owns authoritative game state and validates every move against a precomputed actor↔movie graph
held in Postgres alongside that state.

## Conventions

- **Commits:** Conventional commit format — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **Edits require an explicit request.** Do not modify, create, or delete files unless the user
  specifically asks for a change. Default to investigation, analysis, and proposing diffs in the
  chat. When you believe an edit is warranted, describe it and wait for the go-ahead rather than
  applying it.

## Test-Driven Development

When asked to make code changes, follow TDD unless the user explicitly says to skip tests.

1. **Write a failing test first.** One behavior per test, expressed as the desired end state — not
   the implementation you have in mind.
2. **Run it; confirm it fails red.** The failure must be an assertion failure, not an import,
   syntax, or setup error. A test that errors instead of failing isn't a valid red.
3. **Write the minimum code to pass.** No behavior the test doesn't demand; no speculative
   generality.
4. **Run the test and the surrounding suite; confirm green.** A new test passing while an existing
   one breaks is not done.
5. **Refactor with the suite green,** then re-run.

Guardrails:

- **Never weaken, skip, or delete a test to force a pass.** Fix the code. If the test itself looks
  wrong, stop and say so — don't silently change it.
- **Don't write implementation before the red run.** Writing the test and the code together, then
  running once, defeats the purpose — the red step is what proves the test can fail.
- **Show the red and green runs** in your response. Don't report a step you didn't execute.
- **If the behavior is too unclear to write a test for, ask first** — that ambiguity is a design
  question, not a coding one.
