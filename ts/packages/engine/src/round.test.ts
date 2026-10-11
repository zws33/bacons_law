import { describe, expect, test } from "vitest";
import {
  IllegalStateError,
  ValidationError,
  WrongTypeError,
} from "./errors.js";
import { createActor, createMovie } from "./models.js";
import type { InProgress, RoundOver, RoundState } from "./round.js";
import { createInProgress, forfeit, playMove } from "./round.js";
import {
  APOLLO,
  BILL_PAXTON,
  CAST_AWAY,
  EARLY_ONLY,
  EMPTY_CAST,
  HELEN_HUNT,
  inProgress,
  LONG_CHAIN,
  OUTSIDER,
  TOM_HANKS,
  TOY_STORY,
  TWISTER,
  UNRELATED,
} from "./test-utils/fixtures.js";

/** Narrows a result to `RoundOver`, failing the test if the round is still running. */
const asRoundOver = (result: RoundState): RoundOver => {
  expect(result.status).toBe("roundOver");
  if (result.status !== "roundOver") throw new Error("unreachable");
  return result;
};

/** Narrows a result to `InProgress`, failing the test if the round ended. */
const asInProgress = (result: RoundState): InProgress => {
  expect(result.status).toBe("inProgress");
  if (result.status !== "inProgress") throw new Error("unreachable");
  return result;
};

describe("Group G — input validation (R13)", () => {
  test("TC-21 — rejects playerCount < 2", () => {
    for (const playerCount of [1, 0, -1]) {
      expect(() =>
        createInProgress({ moves: [], currentPlayerIndex: 0, playerCount }),
      ).toThrow(ValidationError);
    }
  });

  test("TC-21 — imposes no upper bound on playerCount", () => {
    expect(
      createInProgress({ currentPlayerIndex: 0, playerCount: 12 }).playerCount,
    ).toBe(12);
  });

  test("TC-22 — rejects an out-of-range currentPlayerIndex", () => {
    const outOfRange = [
      { currentPlayerIndex: 2, playerCount: 2 },
      { currentPlayerIndex: -1, playerCount: 2 },
      { currentPlayerIndex: 5, playerCount: 5 },
    ];
    for (const args of outOfRange) {
      expect(() => createInProgress({ moves: [], ...args })).toThrow(
        ValidationError,
      );
    }
  });

  test("TC-31 — exclusion sets default to empty", () => {
    const state = createInProgress({ currentPlayerIndex: 0, playerCount: 2 });
    expect(state.excludedActorIds.size).toBe(0);
    expect(state.excludedMovieIds.size).toBe(0);
  });
});

describe("Group A — chain construction and turn advance", () => {
  test("TC-01 — valid movie after actor", () => {
    const result = asInProgress(
      playMove(
        inProgress({ moves: [TOM_HANKS], currentPlayerIndex: 1 }),
        CAST_AWAY,
      ),
    );
    expect(result.moves).toEqual([TOM_HANKS, CAST_AWAY]);
    expect(result.currentPlayerIndex).toBe(0);
  });

  test("TC-02 — valid actor after movie", () => {
    const result = asInProgress(
      playMove(inProgress({ moves: [TOM_HANKS, CAST_AWAY] }), HELEN_HUNT),
    );
    expect(result.moves).toEqual([TOM_HANKS, CAST_AWAY, HELEN_HUNT]);
    expect(result.currentPlayerIndex).toBe(1);
  });

  test("TC-08 — the opening move is accepted on an empty chain", () => {
    const result = asInProgress(playMove(inProgress(), TOM_HANKS));
    expect(result.moves).toEqual([TOM_HANKS]);
    expect(result.currentPlayerIndex).toBe(1);
  });

  test("TC-13 — the opening move may be a movie", () => {
    const result = asInProgress(playMove(inProgress(), CAST_AWAY));
    expect(result.moves).toEqual([CAST_AWAY]);
    expect(result.currentPlayerIndex).toBe(1);
  });

  test("TC-25 — a full round plays from an empty chain", () => {
    let state = inProgress();
    const indices: number[] = [];
    for (const move of LONG_CHAIN) {
      state = asInProgress(playMove(state, move));
      indices.push(state.currentPlayerIndex);
    }
    expect(indices).toEqual([1, 0, 1, 0, 1, 0]);
    expect(state.moves).toEqual(LONG_CHAIN);
    expect(state.playerCount).toBe(2);
  });
});

describe("Group E — multiplayer rotation", () => {
  test("TC-12 — rotation wraps for N > 2", () => {
    const result = asInProgress(
      playMove(
        inProgress({
          moves: [TOM_HANKS],
          currentPlayerIndex: 2,
          playerCount: 3,
        }),
        CAST_AWAY,
      ),
    );
    expect(result.currentPlayerIndex).toBe(0);
  });

  test("TC-26 — rotation visits every player once per cycle at N = 4", () => {
    let state = inProgress({ playerCount: 4 });
    const indices: number[] = [];
    for (const move of LONG_CHAIN.slice(0, 4)) {
      state = asInProgress(playMove(state, move));
      indices.push(state.currentPlayerIndex);
    }
    expect(indices).toEqual([1, 2, 3, 0]);
    expect(state.moves).toEqual([TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER]);
  });
});

describe("Group B — connection validation (R2, R3, R6, R11)", () => {
  test("TC-03 — movie whose cast excludes the previous actor", () => {
    const result = asRoundOver(
      playMove(inProgress({ moves: [HELEN_HUNT] }), TOY_STORY),
    );
    expect(result.reason).toBe("unconnected");
    expect(result.loserIndex).toBe(0);
    expect(result.losingMove).toEqual(TOY_STORY);
    expect(result.chain).toEqual([HELEN_HUNT]);
  });

  test("TC-04 — actor absent from the previous movie's cast", () => {
    const result = asRoundOver(
      playMove(inProgress({ moves: [TOM_HANKS, CAST_AWAY] }), OUTSIDER),
    );
    expect(result.reason).toBe("unconnected");
    expect(result.loserIndex).toBe(0);
    expect(result.losingMove).toEqual(OUTSIDER);
    expect(result.chain).toEqual([TOM_HANKS, CAST_AWAY]);
  });

  test("TC-14 — connection is evaluated against the immediately preceding move only", () => {
    const chain = [OUTSIDER, UNRELATED, TOM_HANKS, CAST_AWAY];
    const state = inProgress({ moves: chain });

    expect(asInProgress(playMove(state, HELEN_HUNT)).moves).toEqual([
      ...chain,
      HELEN_HUNT,
    ]);

    // Q98 is in UNRELATED's cast, earlier in the chain, but not in CAST_AWAY's.
    const result = asRoundOver(playMove(state, EARLY_ONLY));
    expect(result.reason).toBe("unconnected");
    expect(result.loserIndex).toBe(0);
    expect(result.losingMove).toEqual(EARLY_ONLY);
    expect(result.chain).toEqual(chain);
  });

  test("TC-17 — a movie with an empty cast connects to nothing", () => {
    const forward = asRoundOver(
      playMove(inProgress({ moves: [TOM_HANKS] }), EMPTY_CAST),
    );
    expect(forward.reason).toBe("unconnected");
    expect(forward.loserIndex).toBe(0);
    expect(forward.losingMove).toEqual(EMPTY_CAST);
    expect(forward.chain).toEqual([TOM_HANKS]);

    const backward = asRoundOver(
      playMove(inProgress({ moves: [EMPTY_CAST] }), TOM_HANKS),
    );
    expect(backward.reason).toBe("unconnected");
    expect(backward.loserIndex).toBe(0);
    expect(backward.losingMove).toEqual(TOM_HANKS);
    expect(backward.chain).toEqual([EMPTY_CAST]);
  });
});

describe("Group C — availability and type (R4, R5, R16)", () => {
  test("TC-05 — repeat actor", () => {
    const result = asRoundOver(
      playMove(inProgress({ moves: [TOM_HANKS, CAST_AWAY] }), TOM_HANKS),
    );
    expect(result.reason).toBe("repeat");
    expect(result.loserIndex).toBe(0);
    expect(result.losingMove).toEqual(TOM_HANKS);
    expect(result.chain).toEqual([TOM_HANKS, CAST_AWAY]);
  });

  test("TC-06 — repeat movie", () => {
    const chain = [TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER, BILL_PAXTON];
    const result = asRoundOver(
      playMove(inProgress({ moves: chain, currentPlayerIndex: 1 }), TWISTER),
    );
    expect(result.reason).toBe("repeat");
    expect(result.loserIndex).toBe(1);
    expect(result.losingMove).toEqual(TWISTER);
    expect(result.chain).toEqual(chain);
  });

  test("TC-09 — actor after actor is a wrong-type programming error", () => {
    const state = inProgress({ moves: [TOM_HANKS], currentPlayerIndex: 1 });
    expect(() => playMove(state, HELEN_HUNT)).toThrow(WrongTypeError);
  });

  test("TC-10 — movie after movie is a wrong-type programming error", () => {
    // TOY_STORY.castIds holds "Q1"; an engine checking cast without type would accept it.
    const state = inProgress({ moves: [TOM_HANKS, CAST_AWAY] });
    expect(() => playMove(state, TOY_STORY)).toThrow(WrongTypeError);
  });

  test("TC-11 — a cross-type ID collision is not a repeat", () => {
    const movieQ77 = createMovie({
      id: "Q77",
      displayText: "Some Movie",
      castIds: ["Q77"],
    });
    const actorQ77 = createActor({
      id: "Q77",
      displayText: "Actor sharing a movie's id",
    });
    const result = asInProgress(
      playMove(inProgress({ moves: [movieQ77] }), actorQ77),
    );
    expect(result.moves).toEqual([movieQ77, actorQ77]);
  });

  test("TC-15 — identity is the ID; display metadata is ignored", () => {
    const renamed = createActor({
      id: "Q1",
      displayText: "T. Hanks",
      imagePath: "/other.jpg",
    });
    const result = asRoundOver(
      playMove(inProgress({ moves: [TOM_HANKS, CAST_AWAY] }), renamed),
    );
    expect(result.reason).toBe("repeat");
    expect(result.loserIndex).toBe(0);
    expect(result.losingMove).toEqual(renamed);
    expect(result.chain).toEqual([TOM_HANKS, CAST_AWAY]);
  });

  test("TC-16 — availability scans the entire chain", () => {
    // The repeat is five moves back, and "Q1" is in APOLLO's cast, so the connection is valid.
    const result = asRoundOver(
      playMove(inProgress({ moves: LONG_CHAIN }), TOM_HANKS),
    );
    expect(result.reason).toBe("repeat");
    expect(result.loserIndex).toBe(0);
    expect(result.losingMove).toEqual(TOM_HANKS);
    expect(result.chain).toEqual(LONG_CHAIN);
  });

  test("TC-20 — type is validated before availability", () => {
    // CAST_AWAY here is both the wrong type and unavailable: type wins, so no Repeat.
    const state = inProgress({
      moves: [TOM_HANKS, CAST_AWAY, HELEN_HUNT, TWISTER],
    });
    expect(() => playMove(state, CAST_AWAY)).toThrow(WrongTypeError);
  });

  test("TC-28 — an excluded entity is unavailable even though the chain is clean", () => {
    const excludedMovie = asRoundOver(
      playMove(
        inProgress({ moves: [TOM_HANKS], excludedMovieIds: ["Q10"] }),
        CAST_AWAY,
      ),
    );
    expect(excludedMovie.reason).toBe("repeat");
    expect(excludedMovie.loserIndex).toBe(0);
    expect(excludedMovie.losingMove).toEqual(CAST_AWAY);
    expect(excludedMovie.chain).toEqual([TOM_HANKS]);

    const excludedActor = asRoundOver(
      playMove(
        inProgress({
          moves: [TOM_HANKS, CAST_AWAY],
          currentPlayerIndex: 1,
          excludedActorIds: ["Q2"],
        }),
        HELEN_HUNT,
      ),
    );
    expect(excludedActor.reason).toBe("repeat");
    expect(excludedActor.loserIndex).toBe(1);
    expect(excludedActor.losingMove).toEqual(HELEN_HUNT);
    expect(excludedActor.chain).toEqual([TOM_HANKS, CAST_AWAY]);
  });

  test("TC-29 — exclusions are per-type", () => {
    // Q10 is CAST_AWAY's id, excluded as an ACTOR; the MOVIE Q10 is not barred by it.
    const result = asInProgress(
      playMove(
        inProgress({ moves: [TOM_HANKS], excludedActorIds: ["Q10"] }),
        CAST_AWAY,
      ),
    );
    expect(result.moves).toEqual([TOM_HANKS, CAST_AWAY]);
  });

  test("TC-30 — exclusions apply to the opening move", () => {
    const result = asRoundOver(
      playMove(
        inProgress({ playerCount: 3, excludedActorIds: ["Q1"] }),
        TOM_HANKS,
      ),
    );
    expect(result.reason).toBe("repeat");
    expect(result.loserIndex).toBe(0);
    expect(result.losingMove).toEqual(TOM_HANKS);
    expect(result.chain).toEqual([]);
  });

  test("TC-31 — cross-round reuse is allowed by default", () => {
    const result = asInProgress(
      playMove(inProgress({ moves: [TOM_HANKS] }), CAST_AWAY),
    );
    expect(result.moves).toEqual([TOM_HANKS, CAST_AWAY]);
  });

  test("TC-33 — availability is evaluated before connection", () => {
    // TWISTER is the right type, already in the chain, and would not have connected to TOM_HANKS.
    const chain = [HELEN_HUNT, TWISTER, BILL_PAXTON, APOLLO, TOM_HANKS];
    const result = asRoundOver(
      playMove(inProgress({ moves: chain, currentPlayerIndex: 1 }), TWISTER),
    );
    expect(result.reason).toBe("repeat");
    expect(result.loserIndex).toBe(1);
    expect(result.losingMove).toEqual(TWISTER);
    expect(result.chain).toEqual(chain);
  });
});

describe("Group D — terminal transitions (R7, R14)", () => {
  test("TC-07 — giving up", () => {
    const result = forfeit(
      inProgress({ moves: [TOM_HANKS], currentPlayerIndex: 1 }),
      "gaveUp",
    );
    expect(result.status).toBe("roundOver");
    expect(result.loserIndex).toBe(1);
    expect(result.losingMove).toBeNull();
    expect(result.chain).toEqual([TOM_HANKS]);
    expect(result.reason).toBe("gaveUp");
  });

  test("TC-34 — the forfeit reason reaches the result unchanged", () => {
    // ForfeitReason is a proper subset of RoundEndReason, so forfeit(state, "unconnected")
    // does not typecheck; the reason is the only observable difference between these two.
    const state = inProgress({ moves: [TOM_HANKS], currentPlayerIndex: 1 });
    const a = forfeit(state, "gaveUp");
    const b = forfeit(state, "deadlineLapsed");
    expect(a.reason).toBe("gaveUp");
    expect(b.reason).toBe("deadlineLapsed");
    expect(a.loserIndex).toBe(1);
    expect(b.loserIndex).toBe(1);
    expect(a.chain).toEqual([TOM_HANKS]);
    expect(b.chain).toEqual([TOM_HANKS]);
    expect(a.losingMove).toBeNull();
    expect(b.losingMove).toBeNull();
  });

  test("TC-24 — operations are inapplicable to a terminal state", () => {
    // The signatures reject a RoundOver at compile time; the cast reaches the runtime guard
    // a deserializing caller would hit.
    const terminal = forfeit(
      inProgress({ moves: [TOM_HANKS], currentPlayerIndex: 1 }),
      "gaveUp",
    );
    const smuggled = terminal as unknown as InProgress;
    expect(() => playMove(smuggled, CAST_AWAY)).toThrow(IllegalStateError);
    expect(() => forfeit(smuggled, "gaveUp")).toThrow(IllegalStateError);
  });
});

describe("Group E — the loser is the player on turn (R8)", () => {
  test("TC-27 — the loser is the player on turn, at any N and any index", () => {
    for (const currentPlayerIndex of [0, 1, 2, 3, 4]) {
      const state = inProgress({
        moves: [TOM_HANKS, CAST_AWAY],
        currentPlayerIndex,
        playerCount: 5,
      });

      const played = asRoundOver(playMove(state, OUTSIDER));
      expect(played.loserIndex).toBe(currentPlayerIndex);
      expect(played.losingMove).toEqual(OUTSIDER);
      expect(played.chain).toEqual([TOM_HANKS, CAST_AWAY]);
      expect(played.reason).toBe("unconnected");

      const forfeited = forfeit(state, "gaveUp");
      expect(forfeited.loserIndex).toBe(currentPlayerIndex);
      expect(forfeited.losingMove).toBeNull();
      expect(forfeited.chain).toEqual([TOM_HANKS, CAST_AWAY]);
      expect(forfeited.reason).toBe("gaveUp");
    }
  });
});

describe("Group F — purity (R10)", () => {
  test("TC-18 — the input state is not mutated", () => {
    const state = inProgress({
      moves: [HELEN_HUNT, TWISTER, BILL_PAXTON],
      currentPlayerIndex: 1,
    });
    const before = structuredClone(state);

    playMove(state, APOLLO); // accepted
    playMove(state, CAST_AWAY); // unconnected
    playMove(state, TWISTER); // repeat
    forfeit(state, "gaveUp");

    expect(state).toEqual(before);
  });

  test("TC-19 — determinism", () => {
    const state = inProgress({ moves: [TOM_HANKS], currentPlayerIndex: 1 });
    expect(playMove(state, CAST_AWAY)).toEqual(playMove(state, CAST_AWAY));
  });
});
