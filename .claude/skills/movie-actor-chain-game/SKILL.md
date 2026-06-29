---
name: movie-actor-chain-game
description: Core rules, domain model, and state machine for the Movie-Actor Chain game, a turn-based game where players alternate naming movies and actors with each answer factually connected to the previous one. Consult this skill whenever working on this game project in any capacity, including implementing or debugging game logic, designing the backend or state model, building or styling the UI, designing UX flows, generating gameplay or test content, writing tests, or making product and feature decisions. Trigger it whenever a conversation touches the movie-actor chain game or its rounds, turns, validation, connection-checking, or scoring, even when the user never says the words rules, skill, or context.
---

# Movie-Actor Chain Game

A turn-based word game played as a chain of alternating entities. Players take turns naming a **movie** or an **actor**, and each answer must connect factually to the previous turn: name an actor who was in the previous movie, or a movie the previous actor was in. The chain continues until someone fails.

## How to use this context

This skill is the **single source of truth for game rules and domain concepts**. It is implementation-agnostic on purpose — it does not assume a data source, UI, network model, or whether validation is automated or human-judged. Build those choices on top of this framework.

When a task is concrete (a component, an endpoint, a schema, a test), map the work back to the vocabulary and state model defined here so naming and behavior stay consistent across sessions. When the rules underdetermine a decision (see *Edge cases* and *Extension boundaries*), surface the ambiguity and propose an option rather than silently inventing a rule.

## Core mechanic

The game has exactly two entity types: **Movie** and **Actor**. Play is a chain of turns, and the required entity type **alternates every turn**:

- Previous turn was a **movie** → the next answer must be an **actor who appeared in that movie**.
- Previous turn was an **actor** → the next answer must be a **movie that actor appeared in**.

So a round looks like `Movie → Actor → Movie → Actor → …` or `Actor → Movie → Actor → Movie → …`, depending on how the opener starts it.

**Worked example of a valid chain:**

```
Inception (movie)
  → Leonardo DiCaprio (actor — was in Inception)
    → Titanic (movie — DiCaprio was in it)
      → Kate Winslet (actor — was in Titanic)
        → The Reader (movie — Winslet was in it)
```

## A turn is valid only if BOTH checks pass

This is the heart of the engine. An answer is accepted only when:

1. **Type check** — it is the correct entity type for this turn (movie vs. actor). Cheap and deterministic.
2. **Connection check** — it is factually linked to the previous entity (this actor was in that movie, or vice versa). This is the hard part, because it requires ground truth.

Plus any optional restrictions the implementation has layered on (timers, no-repeats, etc. — see *Extension boundaries*).

**Failure examples:**

```
Forrest Gump (movie) → "Cast Away"        ✗ wrong type — required an ACTOR, got a movie
Pulp Fiction (movie) → "Brad Pitt"         ✗ connection fails — Pitt was not in Pulp Fiction
Tom Hanks (actor)    → (no answer)          ✗ no answer given
```

## The connection check is the design crux

Every meaningful implementation decision flows from *how you establish ground truth* for "did this actor appear in this movie." Treat this as a first-class design question, not a detail. Common approaches: a structured dataset/API (e.g. a movie database), a precomputed bipartite graph, or LLM judgment. Each has different tradeoffs for latency, cost, offline play, and correctness.

The check is also genuinely fuzzy at the edges, which feeds directly into UX and product decisions:

- **Name resolution** — typos, partial names, "DiCaprio" vs. "Leonardo DiCaprio," disambiguating two movies with the same title across years.
- **What counts as "appeared in"** — cameos, uncredited roles, voice-only roles, archival footage, deleted scenes. The base rules don't decide this; the implementation must.

Decide and document these policies explicitly; they determine how lenient validation feels and whether you need a dispute/challenge mechanism.

## Failure ends the round

A turn fails when **no answer is given** or **the answer is invalid** (wrong type, or not connected). A failing turn ends the round immediately. The round result — chiefly *which player failed* — is then handed to the match layer.

## Two layers: round resolution vs. match progression

Keep these separated. The round engine knows nothing about scoring; the match layer knows nothing about movie facts.

**Round resolution** answers: whose turn is it, what type is required next, is the submitted answer valid, who failed, and when does the round end.

**Match progression** answers: how a failed round affects a player's score/status, whether a player is eliminated, whether a new round starts, when the game ends, and who wins.

### Example win condition (one overlay, not a base rule)

Penalty-point elimination: each round loss gives the failing player one point; a max-score threshold is set before play; reaching it eliminates the player; remaining players keep playing; the game ends when one player remains. This is *an* example match structure — swap it for any other (single life, best-of-N, score targets) without touching round resolution.

## Domain model

| Concept | Meaning |
|---|---|
| Player | A participant. |
| Round | One sequence of alternating turns ending in a failure. |
| Turn | One player's attempt to supply the next valid entity. |
| Entity | A named movie or actor. |
| Entity Type | Whether an entity is a movie or an actor. |
| Prompt Entity | The entity from the previous valid turn (what you must connect to). |
| Required Type | The entity type that must be supplied next. |
| Validation | Checking type correctness + factual connection (+ any restrictions). |
| Penalty | The consequence of a failed turn, at the match layer. |
| Elimination | Whether a player is still active in the match. |

### State to track

Round-level: active players, turn order, current round status, the previous valid entity, the required next type, the submitted response, the validation result, and the failing player.

Match-level: per-player score/penalty count and elimination state, and overall game status/winner.

## Minimal rules engine

The round engine's evaluation loop:

1. Read the previous valid entity (the prompt entity).
2. Infer the required next entity type (the opposite type).
3. Accept the current player's submitted answer.
4. Validate type, then factual connection.
5. Mark the turn success or failure.
6. On failure, end the round and hand off to the match layer.

## Edge cases the base rules leave open

These aren't bugs to fix — they're decisions to make and document, and good things to flag when a task depends on them:

- **The opening move** — who picks the first entity, and is any movie/actor a legal opener?
- **Repeats** — may an entity already used in this round (or match) be reused? The base rules don't forbid it.
- **Disambiguation** — how the system resolves ambiguous or misspelled input before judging connection.
- **"Appeared in" policy** — cameos / voice / uncredited / archival, as above.

## Extension boundaries

These are **optional** and must NOT be assumed by default. If a feature here is in scope, the user will say so:

- Turn timers
- Restrictions on repeated entities
- Formal challenge / dispute resolution
- Difficulty tiers
- Category constraints (genre, era, franchise, region)
- Team-based modes
- Bonus scoring
- AI hints / assist systems

## Mental model

Structurally, the game is a **traversal of a bipartite graph** whose two node sets are actors and movies, with an edge wherever an actor appeared in a movie. A round is a walk along that graph that alternates node sets every step; a player fails when they can't (or wrongly claim to) extend the walk. Gameplay-wise it's a tight loop of recall → validation → failure detection → scoring/elimination → restart.