import { describe, expect, test } from "vitest";
import { ValidationError } from "./errors.js";
import { createActor, createMovie } from "./models.js";

describe("Group G — input validation (R13)", () => {
  test("TC-23 — rejects a blank entity ID", () => {
    expect(() => createActor({ id: "", displayText: "Nameless" })).toThrow(
      ValidationError,
    );
    expect(() => createActor({ id: "  ", displayText: "Whitespace" })).toThrow(
      ValidationError,
    );
    expect(() =>
      createMovie({ id: "Q50", displayText: "Bad Cast", castIds: ["Q1", ""] }),
    ).toThrow(ValidationError);
  });

  test("TC-23 — an empty castIds set is legal data", () => {
    const movie = createMovie({
      id: "Q40",
      displayText: "No Cast On Record",
      castIds: [],
    });
    expect(movie.castIds.size).toBe(0);
  });

  test("TC-23 — rejects a blank movie ID", () => {
    expect(() =>
      createMovie({ id: " ", displayText: "Nameless", castIds: ["Q1"] }),
    ).toThrow(ValidationError);
  });
});
