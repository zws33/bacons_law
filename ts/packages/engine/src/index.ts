// Public API for @baconslaw/engine — the round engine of docs/ENGINE_CONFORMANCE.md.
// Pure state transitions: no I/O, no clock, no randomness (R10, S1).
export {
  IllegalStateError,
  ValidationError,
  WrongTypeError,
} from "./errors.js";
export type { Actor, EntityId, Move, Movie } from "./models.js";
export { createActor, createMovie } from "./models.js";
export type {
  ForfeitReason,
  InProgress,
  RoundEndReason,
  RoundOver,
  RoundState,
} from "./round.js";
export { createInProgress, forfeit, playMove } from "./round.js";
