// Conformance-suite fixtures from docs/ENGINE_CONFORMANCE.md. The QIDs are QID-shaped
// placeholders, not real Wikidata ids — the specific values are load-bearing for the cases
// that stack causes (TC-14, TC-20, TC-33), so do not "simplify" them.

import type { Move } from "../models.js";
import { createActor, createMovie } from "../models.js";
import type { InProgress } from "../round.js";
import { createInProgress } from "../round.js";

export const TOM_HANKS = createActor({ id: "Q1", displayText: "Tom Hanks" });
export const HELEN_HUNT = createActor({ id: "Q2", displayText: "Helen Hunt" });
export const BILL_PAXTON = createActor({
  id: "Q3",
  displayText: "Bill Paxton",
});
export const EARLY_ONLY = createActor({
  id: "Q98",
  displayText: "Actor in an earlier movie only",
});
export const OUTSIDER = createActor({
  id: "Q99",
  displayText: "Unknown Actor",
});

export const CAST_AWAY = createMovie({
  id: "Q10",
  displayText: "Cast Away",
  castIds: ["Q1", "Q2"],
});
export const TOY_STORY = createMovie({
  id: "Q20",
  displayText: "Toy Story",
  castIds: ["Q1"],
});
export const UNRELATED = createMovie({
  id: "Q30",
  displayText: "Unrelated",
  castIds: ["Q99", "Q1", "Q98"],
});
export const EMPTY_CAST = createMovie({
  id: "Q40",
  displayText: "No Cast On Record",
  castIds: [],
});
export const TWISTER = createMovie({
  id: "Q50",
  displayText: "Twister",
  castIds: ["Q2", "Q3"],
});
export const APOLLO = createMovie({
  id: "Q60",
  displayText: "Apollo 13",
  castIds: ["Q1", "Q3"],
});

// Q1 -> {Q1,Q2} -> Q2 -> {Q2,Q3} -> Q3 -> {Q1,Q3}: valid at every step.
export const LONG_CHAIN: readonly Move[] = [
  TOM_HANKS,
  CAST_AWAY,
  HELEN_HUNT,
  TWISTER,
  BILL_PAXTON,
  APOLLO,
];

type StateOverrides = {
  moves?: readonly Move[];
  currentPlayerIndex?: number;
  playerCount?: number;
  excludedActorIds?: Iterable<string>;
  excludedMovieIds?: Iterable<string>;
};

/** `InProgress` with the suite's common defaults: empty chain, player 0 on turn, 2 players. */
export const inProgress = (overrides: StateOverrides = {}): InProgress =>
  createInProgress({
    moves: overrides.moves ?? [],
    currentPlayerIndex: overrides.currentPlayerIndex ?? 0,
    playerCount: overrides.playerCount ?? 2,
    ...(overrides.excludedActorIds
      ? { excludedActorIds: overrides.excludedActorIds }
      : {}),
    ...(overrides.excludedMovieIds
      ? { excludedMovieIds: overrides.excludedMovieIds }
      : {}),
  });
