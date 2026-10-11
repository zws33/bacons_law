---
name: movie-actor-chain-game
description: Vocabulary and mental model for Bacon's Law, a turn-based game where players alternate naming movies and actors, each answer connected to the previous one. Load when working on round or match logic, state models, validation, scoring, or UI for this game, to get the shared terms right. The numbered rules live in docs/ENGINE_CONFORMANCE.md and docs/MATCH_CONFORMANCE.md, which outrank this file.
---

# Movie-Actor Chain Game — vocabulary

**This file defines terms, not rules.** [docs/ENGINE_CONFORMANCE.md](../../../docs/ENGINE_CONFORMANCE.md)
(R1–R17) and [docs/MATCH_CONFORMANCE.md](../../../docs/MATCH_CONFORMANCE.md) (M1–M16) are authoritative
for behavior. If this file and a spec disagree, the spec wins; say so rather than reconciling silently.

## Mental model

The game is a walk on a bipartite graph whose node sets are actors and movies, with an edge wherever an
actor appeared in a movie. A round alternates node sets every step. A player loses the round when they
cannot — or wrongly claim to — extend the walk.

```
Inception → Leonardo DiCaprio → Titanic → Kate Winslet → The Reader
```

## Terms

| Concept | Meaning |
|---|---|
| Player | A participant |
| Round | One chain of alternating turns, ending in exactly one loser |
| Turn | One player's attempt to supply the next move |
| Entity | A named movie or actor. The specs call this a **Move** |
| Entity Type | Movie or actor |
| Prompt Entity | The previous valid move — what the next answer must connect to |
| Required Type | The type that must be supplied next (the opposite of the prompt entity's) |
| Validation | Type check, then availability, then connection. Order is normative (R4→R5→R6) |
| Strike | What losing a round costs at the match layer. Lowest total is best |
| Removed | A player out of the match — strike limit, lapsed deadline, or withdrawal |

## The two layers

**Round engine** — whose turn, what type is required, is the move valid, who lost, has the round ended.
It names a loser, never a winner. It reads `castIds` and nothing else.

**Match layer** — strikes, removal, standings, opener rotation, cross-round exclusions. It never sees a
move and has no opinion about whether a chain is valid.

Keep them separate. The seam is constitutive vs. regulative — see
[ENGINE_CONFORMANCE.md § Where the seam falls](../../../docs/ENGINE_CONFORMANCE.md#where-the-seam-falls).

## Settled, in case you remember otherwise

- **In-round repeats end the round** (R5 clause 1, `reason == Repeat`). Not optional — it is what makes
  a round terminate (R17).
- **Per-turn deadlines are core**, not an extension. A lapse ends the round (`DeadlineLapsed`) and
  removes the player (M5).
- **Ground truth is a precomputed Wikidata graph**, not an API or LLM judgment. An edge the artifact
  does not carry is not a legal move, however true off-graph (R12).
- **There is no "rejected move."** Every invalid submission ends the round.

Still open and worth flagging when a task depends on one: name resolution and disambiguation of user
input, and what counts as "appeared in" (cameos, voice, uncredited, archival) at the ETL cast cap.
