import { expect, test } from "vitest";
import { makeSearchKey } from "./makeSearchKey.js";

test("strips punctuation/symbols and normalizes accents, case, and whitespace", () => {
  const label = "Héllo,  Wőrl$d! 123 $";
  expect(makeSearchKey(label)).toBe("hello worl d 123");
});

test("normalizes hyphenated titles so spacing variants match", () => {
  expect(makeSearchKey("Spider-Man")).toBe("spider man");
});

test("keeps an all-symbol title verbatim instead of producing an empty key", () => {
  expect(makeSearchKey("$")).toBe("$");
});

test("throws when the label has no usable characters", () => {
  expect(() => makeSearchKey("   ")).toThrow(/invalid search key/);
});
