/**
 * R15 — these surface as thrown errors, never as a `RoundState`. A malformed input that
 * resolved to a `RoundOver` would charge a loss to a player who did nothing wrong.
 */
export class ValidationError extends Error {
  // R13 — raised by a constructor on invalid state or move construction.
  override readonly name = "ValidationError";
}

export class IllegalStateError extends Error {
  // R14 — `playMove`/`forfeit` invoked on a terminal state.
  override readonly name = "IllegalStateError";
}

export class WrongTypeError extends Error {
  // R4 — a move that does not alternate type reached `playMove`. A caller-layer defect:
  // the required type is fully determined by the chain.
  override readonly name = "WrongTypeError";
}
