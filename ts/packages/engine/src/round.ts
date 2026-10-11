import {
  IllegalStateError,
  ValidationError,
  WrongTypeError,
} from "./errors.js";
import type { EntityId, Move } from "./models.js";

export type RoundEndReason =
  | "unconnected"
  | "repeat"
  | "gaveUp"
  | "deadlineLapsed";

/** A proper subset of `RoundEndReason`: `forfeit` cannot produce `"unconnected"`. */
export type ForfeitReason = "gaveUp" | "deadlineLapsed";

export type InProgress = {
  readonly status: "inProgress";
  readonly moves: readonly Move[];
  readonly currentPlayerIndex: number;
  readonly playerCount: number;
  readonly excludedActorIds: ReadonlySet<EntityId>;
  readonly excludedMovieIds: ReadonlySet<EntityId>;
};

/** S3 — no winner, placement, score, or strike field. The engine names only a loser. */
export type RoundOver = {
  readonly status: "roundOver";
  readonly loserIndex: number;
  readonly chain: readonly Move[];
  readonly losingMove: Move | null;
  readonly reason: RoundEndReason;
};

export type RoundState = InProgress | RoundOver;

type InProgressInput = {
  moves?: readonly Move[];
  currentPlayerIndex: number;
  playerCount: number;
  excludedActorIds?: Iterable<EntityId>;
  excludedMovieIds?: Iterable<EntityId>;
};

export const createInProgress = (input: InProgressInput): InProgress => {
  const { currentPlayerIndex, playerCount } = input;
  if (!Number.isInteger(playerCount) || playerCount < 2) {
    throw new ValidationError(
      `playerCount must be an integer >= 2, got ${playerCount}`,
    );
  }
  if (
    !Number.isInteger(currentPlayerIndex) ||
    currentPlayerIndex < 0 ||
    currentPlayerIndex >= playerCount
  ) {
    throw new ValidationError(
      `currentPlayerIndex must be an integer in [0, ${playerCount}), got ${currentPlayerIndex}`,
    );
  }
  return {
    status: "inProgress",
    moves: [...(input.moves ?? [])],
    currentPlayerIndex,
    playerCount,
    excludedActorIds: new Set(input.excludedActorIds ?? []),
    excludedMovieIds: new Set(input.excludedMovieIds ?? []),
  };
};

/** The type the chain demands next, or null on an empty chain — either type opens a round (R1). */
const requiredType = (state: InProgress): Move["kind"] | null => {
  const previous = state.moves.at(-1);
  if (previous === undefined) return null;
  return previous.kind === "actor" ? "movie" : "actor";
};

/** R5 — uniqueness is scoped within a type, for both the chain and the exclusion sets. */
const isAvailable = (state: InProgress, move: Move): boolean => {
  const excluded =
    move.kind === "actor" ? state.excludedActorIds : state.excludedMovieIds;
  if (excluded.has(move.id)) return false;
  return !state.moves.some(
    (played) => played.kind === move.kind && played.id === move.id,
  );
};

const connects = (previous: Move, move: Move): boolean => {
  if (previous.kind === "movie" && move.kind === "actor")
    return previous.castIds.has(move.id); // R2
  if (previous.kind === "actor" && move.kind === "movie")
    return move.castIds.has(previous.id); // R3
  return false; // unreachable: the type check (R4) runs first
};

const roundOver = (
  state: InProgress,
  losingMove: Move | null,
  reason: RoundEndReason,
): RoundOver => ({
  status: "roundOver",
  loserIndex: state.currentPlayerIndex, // R8 — the player on turn is the player who failed
  chain: [...state.moves], // R6/R16 — the losing move is never appended
  losingMove,
  reason,
});

/**
 * R14 — the signatures reject a terminal state statically. This guard catches the caller that
 * deserialized one, where it would otherwise be read as an `InProgress` with missing fields.
 */
const requireInProgress = (state: InProgress): void => {
  if (state.status !== "inProgress") {
    throw new IllegalStateError(
      "the round is over; playMove and forfeit accept only InProgress",
    );
  }
};

const accept = (state: InProgress, move: Move): InProgress => ({
  ...state,
  moves: [...state.moves, move],
  // R9 — rotation wraps at any playerCount >= 2.
  currentPlayerIndex: (state.currentPlayerIndex + 1) % state.playerCount,
});

/**
 * Evaluation order is normative: type, then availability, then connection. A move that is both
 * unavailable and unconnected resolves to `"repeat"` (TC-33).
 */
export const playMove = (state: InProgress, move: Move): RoundState => {
  requireInProgress(state);
  const required = requiredType(state);
  if (required !== null && move.kind !== required) {
    // R4 + R15 — a caller-layer defect, never a round outcome.
    throw new WrongTypeError(`expected a ${required} move, got a ${move.kind}`);
  }
  if (!isAvailable(state, move)) return roundOver(state, move, "repeat");
  const previous = state.moves.at(-1);
  if (previous !== undefined && !connects(previous, move)) {
    return roundOver(state, move, "unconnected");
  }
  return accept(state, move);
};

/**
 * R7 — concedes the round, not the match. The engine has no clock (R10), so the session layer
 * decides whether this is a give-up or a lapsed deadline and says which.
 */
export const forfeit = (
  state: InProgress,
  reason: ForfeitReason,
): RoundOver => {
  requireInProgress(state);
  return roundOver(state, null, reason);
};
